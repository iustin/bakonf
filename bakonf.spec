Summary: A configuration file backup tool
Name: bakonf
Version: 0.4.1
Release: 1
License: GPL
Vendor: Iustin Pop
Packager: Iustin Pop <ossdevel-savannah@k1024.org>
Group: Applications/System
URL: http://www
Source0: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-buildroot
BuildArch: noarch
Requires: rpm-python >= 4.1 python-optik tarfile

%description
bakonf is a tool designed to make backups of the configuration
files of a GNU/Linux or Unix-like system. Its aim is to use
various methods in order to reduce the size of the backup to a
reasonable minimum, in order to be useful for remote/unattended
servers.
%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%dir /etc/bakonf
%dir /etc/bakonf/sources
%config /etc/bakonf/bakonf.conf
%config /etc/bakonf/sources/*.sources
/usr/sbin/bakonf.py
/var/lib/bakonf
%doc /usr/share/doc/%{name}-%{version}
/etc/cron.d/bakonf

%changelog
* Thu Dec 12 2002 Iustin Pop <iusty@yahoo.com> 0.3-1
- Version 0.3

* Wed Dec 11 2002 Iustin Pop <iusty@yahoo.com> 
- Initial build.
