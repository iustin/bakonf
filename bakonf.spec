Summary: A configuration file backup tool
Name: bakonf
Version: 0.6.0
Release: 1
License: GPL
Vendor: Iustin Pop
Packager: Iustin Pop <iusty@k1024.org>
Group: Applications/System
URL: http://www.nongnu.org/bakonf/
Source0: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-buildroot
BuildArch: noarch
#Requires: python-optik tarfile

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
%config /etc/bakonf/bakonf.xml
%config /etc/bakonf/sources/*.xml
/usr/bin/bakonf
/var/lib/bakonf
%doc /usr/share/doc/%{name}-%{version}
/usr/share/man/*/*
/etc/cron.d/bakonf

%changelog
* Fri Jan 01 2010 Iustin Pop <iusty@k1024.org> 0.6.0-1
- Add compatiblity with python 3.x
- Many changes to the configuration file format and archive layout

* Sat Dec 06 2008 Iustin Pop <iusty@k1024.org> 0.5.3-1
- Fix compatibility with python 2.5

* Sat Jan 26 2008 Iustin Pop <iusty@k1024.org> 0.5.2-1
- Fix charset/encoding issues

* Fri Dec 20 2002 Iustin Pop <iusty@k1024.org> 0.5-1
- Major upgrade; now xml config, no more rpm dependency, new docs

* Tue Dec 17 2002 Iustin Pop <iusty@k1024.org> 0.4.1-1
- Version 0.4.1 - bugfixing, added usermanual to the rpm

* Thu Dec 12 2002 Iustin Pop <iusty@k1024.org> 0.3-1
- Version 0.3

* Wed Dec 11 2002 Iustin Pop <iusty@k1024.org>
- Initial build.
