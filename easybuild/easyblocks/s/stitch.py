##
# Copyright 2009-2023 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/easybuilders/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
"""
EasyBuild support for SCOTCH, implemented as an easyblock

@author: Pieter D (Ghent University)
@author: Jens Timmerman (Ghent University)
"""
import os
from distutils.version import LooseVersion

import easybuild.tools.toolchain as toolchain
from easybuild.framework.easyblock import EasyBlock
from easybuild.framework.easyconfig import CUSTOM
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.filetools import apply_regex_substitutions, change_dir, copy_dir, copy_file
from easybuild.tools.filetools import remove_file, write_file
from easybuild.tools.run import run_cmd

DEFAULT_BUILD_CMD = 'make'
DEFAULT_BUILD_TARGET = ''
DEFAULT_TEST_CMD = 'make'

class EB_stitch(EasyBlock):
    """Support for building/installing stitch."""

#     @staticmethod
#     def extra_options(extra_vars=None):
#         """Define custom easyconfig parameters specific to Scotch."""
#         extra_vars = {
#             'threadedmpi': [None, "Use threaded MPI calls.", CUSTOM],
#         }
#         return EasyBlock.extra_options(extra_vars)

    def configure_step(self):
        """Configure SCOTCH build: locate the template makefile, copy it to a general Makefile.inc and patch it."""

        # Currently, Stitch is part of the spparks source code. This might change in future versions,
        # so the srdir_stitch may change
        self.srcdir_stitch = os.path.join(self.cfg['start_dir'], 'lib', 'stitch', 'libstitch')

        # To configure libstitch, we alter the makefile
        makefile_stitch = os.path.join(self.srcdir_stitch, 'Makefile')

        regex_subs_stitch = [
            (r"^(CC\s*=\s*).*$", r"\1%s" % os.environ['MPICC']),
            (r"^(CXX\s*=\s*).*$", r"\1%s" % os.environ['MPICXX'])
        ]
        apply_regex_substitutions(makefile_stitch, regex_subs_stitch)

        # pick template makefile
#        comp_fam = self.toolchain.comp_family()
#        if comp_fam == toolchain.INTELCOMP:  # @UndefinedVariable
#            makefilename = 'Makefile.inc.x86-64_pc_linux2.icc'
#        elif comp_fam == toolchain.GCC:  # @UndefinedVariable
#            makefilename = 'Makefile.inc.x86-64_pc_linux2'
#        else:
#            raise EasyBuildError("Unknown compiler family used: %s", comp_fam)

#         srcdir = os.path.join(self.cfg['start_dir'], 'src')
# 
#         # create Makefile.inc
#         makefile_inc = os.path.join(srcdir, 'Makefile.inc')
#         copy_file(os.path.join(srcdir, 'Make.inc', makefilename), makefile_inc)
#         self.log.debug("Successfully copied Makefile.inc to src dir: %s", makefile_inc)
# 
#         # the default behaviour of these makefiles is still wrong
#         # e.g., compiler settings, and we need -lpthread
#         regex_subs = [
#             (r"^CCS\s*=.*$", "CCS\t= $(CC)"),
#             (r"^CCP\s*=.*$", "CCP\t= $(MPICC)"),
#             (r"^CCD\s*=.*$", "CCD\t= $(MPICC)"),
#             # append -lpthread to LDFLAGS
#             (r"^LDFLAGS\s*=(?P<ldflags>.*$)", r"LDFLAGS\t=\g<ldflags> -lpthread"),
#             # prepend -L${EBROOTZLIB}/lib to LDFLAGS
#             (r"^LDFLAGS\s*=(?P<ldflags>.*$)", r"LDFLAGS\t=-L${EBROOTZLIB}/lib \g<ldflags>"),
#         ]
#         apply_regex_substitutions(makefile_inc, regex_subs)
# 
#         # change to src dir for building
#         change_dir(srcdir)

    def test_step(self):
        """
        Test the compilation
        - default: None
        """

        test_cmd = self.cfg.get('test_cmd') or DEFAULT_TEST_CMD
        if self.cfg['runtest'] or test_cmd != DEFAULT_TEST_CMD:
            cmd = ' '.join([
                self.cfg['pretestopts'],
                test_cmd,
                self.cfg['runtest'],
                self.cfg['testopts'],
            ])
            (out, _) = run_cmd(cmd, log_all=True, simple=False)

            return out

    def build_step(self, verbose=False, path=None):
        """
        Start the actual build
        - typical: make -j X
        """

        # Change to stitch sourcedir. This may need to be removed if Stitch is ever separated from the spparks sources
        change_dir(self.srcdir_stitch)

        paracmd = ''
        if self.cfg['parallel']:
            paracmd = "-j %s" % self.cfg['parallel']

        targets = self.cfg.get('build_cmd_targets') or DEFAULT_BUILD_TARGET
        # ensure strings are converted to list
        targets = [targets] if isinstance(targets, str) else targets

        for target in targets:
            cmd = ' '.join([
                self.cfg['prebuildopts'],
                self.cfg.get('build_cmd') or DEFAULT_BUILD_CMD,
                target,
                paracmd,
                self.cfg['buildopts'],
            ])
            self.log.info("Building target '%s'", target)

            (out, _) = run_cmd(cmd, path=path, log_all=True, simple=False, log_output=verbose)

        return out

    def install_step(self):
        """Install by copying files and creating group library file."""

        self.log.debug("Installing stitch by copying files")

        headers = ['stitch.h', 'sqlite3.h']
        libs = ['libstitch.a']

        for header in headers:
            copy_file(os.path.join(self.srcdir_stitch, header), os.path.join(self.installdir, 'include', header))

        for lib in libs:
            copy_file(os.path.join(self.srcdir_stitch, lib), os.path.join(self.installdir, 'lib', lib))

