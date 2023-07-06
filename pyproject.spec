%global common_description %{expand:
The hpc resource reservation app helps managing VSC projects.
}

Name:           python3-django-iprestrict-redux
Summary:        django iprestrict fork
Version:        1.9.0
Release:        %{gittag}.1.ug%{?dist}

License:        ARR

URL:            https://github.com/sztamas/django-iprestrict-redux
Source0:        https://github.com/sztamas/django-iprestrict-redux/archive/%{version}/django-iprestrict-redux-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros


%description %{common_description}

%prep
%autosetup -p1


# this needs a more recent rpmbuild
#%%generate_buildrequires
## add -r to test (and also include runtime deps as buildrequires)
#%%pyproject_buildrequires


%build
%pyproject_wheel


%install
%pyproject_install
# todo make this dynamic
%pyproject_save_files iprestrict
chmod 755 $(find %{buildroot}/%{python3_sitelib}/ -type d)
chmod 644 $(find %{buildroot}/%{python3_sitelib}/ -type f)

%files -f %{pyproject_files}
%license LICENSE
%doc README.md

%changelog
* Fri May 28 2021 hpc-admin <hcp-admin@lists.ugent.be> - 0.0.1
- Init
