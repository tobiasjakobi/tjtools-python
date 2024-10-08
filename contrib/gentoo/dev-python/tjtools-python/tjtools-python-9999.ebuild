# Copyright 1999-2024 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DISTUTILS_USE_PEP517=hatchling
PYTHON_COMPAT=( python3_{11..13} )
inherit distutils-r1 git-r3

DESCRIPTION="Some Python tools that I use on most of my systemss"
HOMEPAGE="https://github.com/tobiasjakobi/tjtools-python"
EGIT_REPO_URI="https://github.com/tobiasjakobi/tjtools-python.git"

KEYWORDS="x86 amd64"

LICENSE="GPL-2"
SLOT="0"

RDEPEND="
	>=dev-python/dbus-python-1.3.2[${PYTHON_USEDEP}]
	>=dev-python/i3ipc-2.2.1[${PYTHON_USEDEP}]
	>=dev-python/python-magic-0.4.27[${PYTHON_USEDEP}]
	>=dev-python/python-systemd-235[${PYTHON_USEDEP}]
	>=media-libs/mutagen-1.47.0[${PYTHON_USEDEP}]
"
