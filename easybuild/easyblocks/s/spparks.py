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
import glob
from distutils.version import LooseVersion

import easybuild.tools.toolchain as toolchain
from easybuild.framework.easyblock import EasyBlock
from easybuild.framework.easyconfig import CUSTOM
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.filetools import apply_regex_substitutions, change_dir, copy_dir, copy_file, symlink
from easybuild.tools.filetools import remove_file, write_file
from easybuild.tools.run import run_cmd
from easybuild.tools.systemtools import get_shared_lib_ext

DEFAULT_BUILD_CMD = 'make'
DEFAULT_TEST_CMD = 'make'

class EB_spparks(EasyBlock):
    """Support for building/installing SPPARKS."""

    def __init__(self, *args, **kwargs):
        super(EB_spparks, self).__init__(*args, **kwargs)

        # Name of the 'target machine' as it is know by the spparks build system
        self.machine = 'eb'

#     @staticmethod
#     def extra_options(extra_vars=None):
#         """Define custom easyconfig parameters specific to Scotch."""
#         extra_vars = {
#             'threadedmpi': [None, "Use threaded MPI calls.", CUSTOM],
#         }
#         return EasyBlock.extra_options(extra_vars)

    def configure_step(self):
        """Configure SCOTCH build: locate the template makefile, copy it to a general Makefile.inc and patch it."""

        self.spparks_srcdir = os.path.join(self.cfg['start_dir'], 'src')

        # modify makefile for spparks, using the *.mpi makefile as starting point
        makefile_include_dir = os.path.join(self.spparks_srcdir, 'MAKE')
        makefile_spparks = os.path.join(makefile_include_dir, 'Makefile.%s' % self.machine)
        copy_file(os.path.join(makefile_include_dir, 'Makefile.mpi'), makefile_spparks)

        if self.toolchain.options['cstd']:
            ccflags = '-std=%s %s' % (self.toolchain.options['cstd'], os.environ['OPTFLAGS'])
        else:
            ccflags = os.environ['OPTFLAGS']

        if self.toolchain.options['pic']:
             pic = '-%s' % self.toolchain.options.options_map['pic']
        else:
             pic = ''

        regex_subs_spparks = [
            (r"^(CC\s*=\s*).*$", r"\1%s" % os.environ['MPICXX']),  # TODO: put in logic to test: if its an MPI based toolchain, use MPICXX, otherwise use CXX
            (r"^(LINK\s*=\s*).*$", r"\1%s" % os.environ['MPICXX']),  # TODO: see above
            (r"^(CCFLAGS\s*=\s*).*$", r"\1%s" % ccflags),
            (r"^(SHFLAGS\s*=\s*).*$", r"\1%s" % pic),
            (r"^(LINKFLAGS\s*=\s*).*$", r"\1%s" % os.environ['LDFLAGS']),
        ]
        apply_regex_substitutions(makefile_spparks, regex_subs_spparks)

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

    def build_step(self, verbose=False, path=None):
        """
        Start the actual build
        - typical: make -j X
        """

        # Change dir to where the Makefile is
        change_dir(self.spparks_srcdir)

        paracmd = ''
        if self.cfg['parallel']:
            paracmd = "-j %s" % self.cfg['parallel']

        # In our configure_step, we generate a Makefile.eb. Thus, we hardcode that 'eb' as a build target here.
        # These are the document targets to build the executable, shared library, and static library
        # However, building the shared and static lib currently fails with missing file errors, e.g. app_cpm.cpp
        # targets = ['eb', '-f Makefile.shlib eb', '-f Makefile.lib eb']

        # The mode=shlib is _not_ documented, but is one of the targets shown in the makefile, and seems to succesfully
        # build the shared library
        targets = [self.machine, 'mode=shlib %s' % self.machine, 'mode=lib %s' % self.machine]

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

        self.log.debug("Installing spparks by copying files")

        binaries = ['spk']
        headers = list(glob.glob(os.path.join(self.spparks_srcdir, '*.h')))
        shared_libs = ['libspparks']
        static_libs = ['libspparks']

        self.log.debug("headers: %s" % headers)

        for binary in binaries:
            binary_name = '%s_%s' % (binary, self.machine)
            src = os.path.join(self.spparks_srcdir, binary_name)
            target = os.path.join(self.installdir, 'bin', binary_name)
            copy_file(src, target)
            # Create link e.g. spk => spk.eb
            symlink(
                target, 
                os.path.join(
                    self.installdir, 
                    'bin', 
                    binary
                )
            )

        for header in headers:
            copy_file(header, os.path.join(self.installdir, 'include', os.path.basename(header)))

        for lib in shared_libs:
            # TODO: should probably use something like the SHLIB_EXT template, but no clue how we can do this in an EasyBlock?
            libname = '%s_%s.%s' % (lib, self.machine, get_shared_lib_ext())
            src = os.path.join(self.spparks_srcdir, libname)
            target = os.path.join(self.installdir, 'lib', libname)
            copy_file(src, target)
            # todo: create link
            symlink(target, os.path.join(self.installdir, 'lib', '%s.%s' % (lib, get_shared_lib_ext())))

        for lib in static_libs:
            libname = '%s_%s.a' % (lib, self.machine)
            src = os.path.join(self.spparks_srcdir, libname)
            target = os.path.join(self.installdir, 'lib', libname)
            copy_file(src, target)
            # todo: create link
            symlink(target, os.path.join(self.installdir, 'lib', '%s.a' % lib))
