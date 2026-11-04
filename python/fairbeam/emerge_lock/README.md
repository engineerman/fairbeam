# EMerge managed-venv lock

`requirements.in` pins the single top-level package (`emerge==3.0.0b12`). `win_amd64-cp313.txt` is the
hash-locked full dependency set for CPython 3.13 on Windows x86-64 (wheels only). It was generated with
`uv pip compile python/fairbeam/emerge_lock/requirements.in --generate-hashes --python-version 3.13 --python-platform x86_64-pc-windows-msvc --only-binary=:all: --no-header -o python/fairbeam/emerge_lock/win_amd64-cp313.txt`.
Regenerating it changes the file's SHA-256, which `emerge_runtime.PIN["lock_sha256"]` must match. An upgrade is a new plan task.
