# make-dynpart-mappings for the GTS9 Fedora port

Vendored unmodified from
https://gitlab.com/flamingradian/make-dynpart-mappings at commit
`f883b0bca53634d7df1bbeb5e1f8ed7907d2ab74` (2022-08-29).  The upstream
project has no tags or releases; the RPM version is this port's own.

The tool reads the Android `super` partition's liblp metadata and creates
device-mapper linear mappings for the logical partitions, so the Fedora
rootfs can mount `/dev/mapper/vendor` and the other Android parts.

License: GPL-3.0-only (main program) and Apache-2.0 (`3rdparty/metadata_format.h`).
