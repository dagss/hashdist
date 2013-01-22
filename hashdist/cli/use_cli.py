import os
from os.path import join as pjoin

from .main import register_subcommand

@register_subcommand
class Use(object):
    """
    Prints instructions to set up profile in the current shell

    The profile will be built if it is not available.

    The normal use of this command is to source it into the current
    shell, e.g.::

        source <(hdist env path/to/profile/spec myprofile)
    """

    command = 'use'

    @staticmethod
    def setup(ap):
        ap.add_argument('path', help='path to YAML profile specification')
        ap.add_argument('profile', nargs='?', help='name of profile (default: "default")')

    @staticmethod
    def run(ctx, args):
        from ..frontend import build_profile
        if not args.profile:
            args.profile = 'default'
        build_profile(ctx.config, ctx.logger, args.path, args.profile)

