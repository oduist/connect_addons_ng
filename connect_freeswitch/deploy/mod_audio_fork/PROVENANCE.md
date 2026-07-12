# mod_audio_fork provenance

This directory is a source snapshot of
[`W1ck3dZA/mod_audio_fork`](https://github.com/W1ck3dZA/mod_audio_fork) at
commit `d997d1cd96aac626a69a2de73875a3d6c08b0a7e` (2026-02-10).

The fork descends from the drachtio/jambonz FreeSWITCH modules. The initial
commit contained this copyright and licensing notice:

> Copyright 2023, Drachtio Communications Services, LLC
>
> This software is provided under a dual-licensing scheme, described in the
> jambonz `freeswitch-modules` `COPYING` file.

The upstream fork later deleted its `LICENSE` file while leaving a README link
to it. Consequently, this snapshot must not be described as MIT-licensed. Its
use and redistribution remain subject to the original dual-license terms. The
source is vendored to make builds reproducible after the original drachtio and
jambonz repositories became unavailable.

Local integration changes are limited to whitespace normalization so the
snapshot passes repository checks; there are no semantic source changes.

The upstream C/C++/header sources, `Makefile.am`, `CMakeLists.txt` and
`UPSTREAM-LICENSE` are kept byte-for-byte as snapshotted. Two integration
artifacts were added around them (never editing the upstream files):

1. `Makefile` — FreeSWITCH's in-tree module build ignores the upstream
   `Makefile.am` entirely and, by default, compiles only `mod_audio_fork.c`.
   This plain in-tree `Makefile` declares the extra C++ sources and the
   external libraries (libwebsockets, boost, stdc++) via modmake.rules'
   `LOCAL_OBJS`/`LOCAL_LDFLAGS_POST` so the whole module links correctly.
   modmake.rules only auto-generates a stub Makefile when none exists, so this
   file is honored.

2. A `-Werror` neutralization in `connect_freeswitch/deploy/Dockerfile` (a
   `sed` pass after `./configure`), because the vendored C source predates
   FreeSWITCH's strict module flags (`-Werror -pedantic
   -Wdeclaration-after-statement`).
