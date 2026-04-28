import os
from logging import getLogger

from odoo import models
from odoo.modules import Manifest
from odoo.tools.constants import EXTERNAL_ASSET

from odoo.addons.base.models.ir_asset import (
    _glob_static_file,
    can_aggregate,
    fs2web,
    is_wildcard_glob,
)

_logger = getLogger(__name__)


class IrAsset(models.Model):
    _inherit = 'ir.asset'

    def _get_paths(self, path_def, installed):
        """Windows-safe override that keeps addon static path security check intact."""
        paths = None
        path_def = fs2web(path_def)
        path_parts = [part for part in path_def.split('/') if part]
        addon = path_parts[0]
        addon_manifest = Manifest.for_addon(addon, display_warning=False)

        safe_path = False
        if addon_manifest:
            if addon not in installed:
                raise Exception(
                    f"""Unallowed to fetch files from addon {addon} for file {path_def}. """
                    f"""Addon {addon} is not installed"""
                )
            addons_path = addon_manifest.addons_path
            full_path = os.path.normpath(os.path.join(addons_path, *path_parts))
            static_prefix = os.path.normpath(os.path.join(addon_manifest.path, 'static', ''))
            # On Windows, separators and casing can differ even for equivalent paths.
            if os.path.normcase(full_path).startswith(os.path.normcase(static_prefix)):
                paths_with_timestamps = _glob_static_file(full_path)
                paths = [
                    (fs2web(absolute_path[len(addons_path):]), absolute_path, timestamp)
                    for absolute_path, timestamp in paths_with_timestamps
                ]
                safe_path = True

        if not paths and not can_aggregate(path_def):
            paths = [(path_def, EXTERNAL_ASSET, -1)]

        if not paths and not is_wildcard_glob(path_def):
            paths = [(path_def, None, None)]

        if not paths:
            msg = f'IrAsset: the path "{path_def}" did not resolve to anything.'
            if not safe_path:
                msg += ' It may be due to security reasons.'
            _logger.warning(msg)

        return paths
