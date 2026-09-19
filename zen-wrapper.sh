#!/bin/bash
export MOZ_DISABLE_CONTENT_SANDBOX=1
export MOZ_DISABLE_RDD_SANDBOX=1
export MOZ_DISABLE_GPU_SANDBOX=1
export MOZ_FAKE_NO_SANDBOX=1
export MOZ_WEBRENDER=0
# Android denies reopening memfd through /proc. Gecko's parent then uses
# POSIX shared memory while children still expect memfd seals. Keep its
# size checks but opt out of sealing consistently in every process.
export MOZ_SHM_NO_SEALS=1
exec /home/pixel/.tarball-installations/zen/zen "$@"
