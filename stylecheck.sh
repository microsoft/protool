#!/bin/bash

pushd "${VIRTUAL_ENV}" > /dev/null

python -m pylint --rcfile=pylintrc protool
python -m mypy --ignore-missing-imports protool/

python -m pylint --rcfile=pylintrc tests
python -m mypy --ignore-missing-imports tests/

popd > /dev/null

