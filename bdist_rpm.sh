#!/bin/bash

set -e
set -x

specfile=pyproject.spec

NAME=$(grep "Name:.*python" $specfile | tr -s " " |  awk '{print $2;}')
VERSION=$(grep "Version:.*[0-9]" $specfile | tr -s " " |  awk '{print $2;}')
GITTAG=$(git log --format=%ct.%h -1)

rm -Rf BUILD SOURCES SPECS SRPMS RPMS BUILDROOT LOCAL
mkdir -p BUILD SOURCES SPECS SRPMS RPMS BUILDROOT LOCAL

git archive --prefix $NAME-$VERSION/ --format tar.gz -o SOURCES/django-iprestrict-redux-$VERSION.tar.gz HEAD
cp $specfile "SPECS"

sudo dnf install -y python3-importlib-metadata python3-toml python3-wheel


export PYTHONUSERBASE=$PWD/LOCAL

pip3 install --user 'pip == 19.3.1'

export PATH=$PYTHONUSERBASE/bin:$PATH
$PYTHONUSERBASE/bin/pip3 install --user 'poetry > 1.0.0'
$PYTHONUSERBASE/bin/pip3 install --user 'poetry < 1.0.0'
$PYTHONUSERBASE/bin/pip3 install --user 'packaging >= 17.0'

rpmbuild -ba --define "gittag ${GITTAG}" --define "_topdir $PWD" SPECS/$specfile
rpmrebuild "--change-spec-requires=sed -e '/sentry-sdk\|requests-mock\|pytest/d'"  --directory RPMS -n -p RPMS/noarch/*.rpm
