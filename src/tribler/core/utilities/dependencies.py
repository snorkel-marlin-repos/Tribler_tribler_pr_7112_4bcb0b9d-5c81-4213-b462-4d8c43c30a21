"""
This file lists the python dependencies for Tribler.

Note that this file should not depend on any external modules itself other than builtin ones.
"""
import logging
import re
import tribler
from enum import Enum
from typing import Iterator, Optional
from tribler.core.utilities.path_util import Path

# fmt: off

logger = logging.getLogger(__name__)

Scope = Enum('Scope', 'core gui')

# Exceptional pip packages where the name does not match with actual import.
package_to_import_mapping = {
    'Faker': 'faker',
    'sentry-sdk': 'sentry_sdk'
}

# pylint: disable=import-outside-toplevel

def get_dependencies(scope: Scope) -> Iterator[str]:
    def _get_path_to_requirements_txt() -> Optional[Path]:
        root_path = Path(tribler.__file__).parent.parent.parent
        if scope == Scope.core:
            return root_path / 'requirements-core.txt'
        if scope == Scope.gui:
            return root_path / 'requirements.txt'
        raise AttributeError(f'Scope is {scope} but should be in {[s for s in Scope]}')  # pylint: disable=unnecessary-comprehension

    return _get_pip_dependencies(_get_path_to_requirements_txt())


def _extract_libraries_from_requirements(text: str) -> Iterator[str]:
    logger.debug(f'requirements.txt content: {text}')
    for library in filter(None, text.split('\n')):
        pip_package = re.split(r'[><=~]', library, maxsplit=1)[0]
        yield package_to_import_mapping.get(pip_package, pip_package)


def _get_pip_dependencies(path_to_requirements: Path) -> Iterator[str]:
    logger.info(f'Getting dependencies from: {path_to_requirements}')
    return _extract_libraries_from_requirements(path_to_requirements.read_text())
