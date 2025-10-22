import logging
import time
import uuid
from dataclasses import dataclass, field

from PyQt5 import uic

from tribler.core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler.core.utilities.utilities import Query, to_fts_query

from tribler.gui.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler.gui.tribler_request_manager import TriblerNetworkRequest
from tribler.gui.utilities import connect, get_ui_file_path, tr
from tribler.gui.widgets.tablecontentmodel import SearchResultsModel

widget_form, widget_class = uic.loadUiType(get_ui_file_path('search_results.ui'))


def format_search_loading_label(search_request):
    data = {
        "total_peers": len(search_request.peers),
        "num_complete_peers": len(search_request.peers_complete),
        "num_remote_results": len(search_request.remote_results),
    }

    return (
        tr(
            "Remote responses: %(num_complete_peers)i / %(total_peers)i"
            "\nNew remote results received: %(num_remote_results)i"
        )
        % data
    )


@dataclass
class SearchRequest:
    uuid: uuid
    query: Query
    peers: set
    peers_complete: set = field(default_factory=set)
    remote_results: list = field(default_factory=list)

    @property
    def complete(self):
        return self.peers == self.peers_complete


class SearchResultsWidget(AddBreadcrumbOnShowMixin, widget_form, widget_class):
    def __init__(self, parent=None):
        widget_class.__init__(self, parent=parent)
        self._logger = logging.getLogger(self.__class__.__name__)

        try:
            self.setupUi(self)
        except SystemError:
            pass

        self.last_search_time = None
        self.last_search_query = None
        self.hide_xxx = None
        self.search_request = None

    def initialize(self, hide_xxx=False):
        self.hide_xxx = hide_xxx
        self.results_page.initialize_content_page(hide_xxx=hide_xxx)
        self.results_page.channel_torrents_filter_input.setHidden(True)
        connect(self.timeout_progress_bar.timeout, self.show_results)
        connect(self.show_results_button.clicked, self.show_results)

    @property
    def has_results(self):
        return self.last_search_query is not None

    def show_results(self, *_):
        if self.search_request is None:
            # Fixes a race condition where the user clicks the show_results button before the search request
            # has been registered by the Core
            return
        self.timeout_progress_bar.stop()
        query = self.search_request.query
        self.results_page.initialize_root_model(
            SearchResultsModel(
                channel_info={
                    "name": (tr("Search results for %s") % query.original_query)
                    if len(query.original_query) < 50
                    else f"{query.original_query[:50]}..."
                },
                endpoint_url="search",
                hide_xxx=self.results_page.hide_xxx,
                text_filter=to_fts_query(query.fts_text),
                tags=list(query.tags),
                type_filter=[REGULAR_TORRENT],
            )
        )
        self.setCurrentWidget(self.results_page)

        # After transitioning to the page with search results, we refresh the viewport since some rows might have been
        # rendered already with an incorrect row height.
        self.results_page.run_brain_dead_refresh()

    def check_can_show(self, query):
        if (
            self.last_search_query == query
            and self.last_search_time is not None
            and time.time() - self.last_search_time < 1
        ):
            self._logger.info("Same search query already sent within 500ms so dropping this one")
            return False
        return True

    def search(self, query: Query) -> bool:
        if not self.check_can_show(query.original_query):
            return False

        fts_query = to_fts_query(query.original_query)
        if not fts_query:
            return False

        self.last_search_query = query.original_query
        self.last_search_time = time.time()

        # Trigger remote search
        def register_request(response):
            self._logger.info(f'Request registered: {response}')
            self.search_request = SearchRequest(response["request_uuid"], query, set(response["peers"]))
            self.state_label.setText(format_search_loading_label(self.search_request))
            self.timeout_progress_bar.start()
            self.setCurrentWidget(self.loading_page)

        params = {'txt_filter': fts_query, 'hide_xxx': self.hide_xxx, 'tags': list(query.tags)}
        TriblerNetworkRequest('remote_query', register_request, method="PUT", url_params=params)
        return True

    def reset(self):
        if self.currentWidget() == self.results_page:
            self.results_page.go_back_to_level(0)

    def update_loading_page(self, remote_results):
        if (
            not self.search_request
            or remote_results.get("uuid") != self.search_request.uuid
            or self.currentWidget() == self.results_page
        ):
            return
        peer = remote_results["peer"]
        self.search_request.peers_complete.add(peer)
        self.search_request.remote_results.append(remote_results.get("results", []))
        self.state_label.setText(format_search_loading_label(self.search_request))
        if self.search_request.complete:
            self.show_results()
