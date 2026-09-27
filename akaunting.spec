Summary:	Online double-entry accounting
Name:		akaunting
Version:	3.2.4
Release:	1
License:	BUSL-1.1
Group:		Applications/Productivity
URL:		https://akaunting.com/
Source0:	https://github.com/akaunting/akaunting/archive/refs/tags/%{version}.tar.gz#/akaunting-%{version}.tar.gz
# composer install --no-dev --prefer-dist --ignore-platform-req=php
# plus bootstrap/cache from package discovery. No network at build time.
Source1:	akaunting-%{version}-vendor.tar.xz
# npm install && npx mix --production
Source2:	akaunting-%{version}-assets.tar.xz
Source3:	akaunting.env
Source4:	README.install.omv
BuildArch:	noarch
Requires:	php-cli
Requires:	php-bcmath
Requires:	php-curl
Requires:	php-gd
Requires:	php-intl
Requires:	php-mbstring
Requires:	php-mysqli
Requires:	php-pdo
Requires:	php-pdo_mysql
Requires:	php-phar
Requires:	php-tokenizer
Requires:	php-xml
Requires:	php-zip
Requires:	php-fpm
Requires:	akaunting-webserver-integration = %{EVRD}
Recommends:	mariadb
Requires(post):	%{_bindir}/runuser

%description
Akaunting is a web accounting application for invoicing, bills,
banking, and reports.

Version %{version} is published under the Business Source License 1.1.
Production use is limited to one company, two users, and one thousand
invoices, and the software may not be offered as an accounting service
to third parties. Four years after publication the same code is
licensed under GPLv3.

See README.install.omv after installation. MariaDB is expected on the
local host.

%package nginx
Summary:	nginx and php-fpm integration for Akaunting
Group:		Applications/Productivity
Requires:	%{name} = %{EVRD}
Requires:	nginx
Requires:	php-fpm
Provides:	akaunting-webserver-integration = %{EVRD}

%description nginx
nginx site for Akaunting. The site is installed disabled; symlink it
into sites-enabled and start php-fpm@akaunting.

%package apache
Summary:	Apache and php-fpm integration for Akaunting
Group:		Applications/Productivity
Requires:	%{name} = %{EVRD}
Requires:	apache-base
Requires:	apache-mod_proxy
Requires:	apache-mod_proxy_fcgi
Requires:	apache-mod_rewrite
Requires:	php-fpm
Provides:	akaunting-webserver-integration = %{EVRD}

%description apache
Apache snippet for Akaunting. Point a virtual host at
/srv/www/akaunting and enable mod_proxy_fcgi.

%prep
%autosetup -p1 -n akaunting-%{version}
tar -xf %{SOURCE1}
tar -xf %{SOURCE2}

%build

%install
cp %{SOURCE4} .
install -d %{buildroot}/srv/www/%{name}
cp -a . %{buildroot}/srv/www/%{name}/

rm -rf %{buildroot}/srv/www/%{name}/.git \
	%{buildroot}/srv/www/%{name}/.github \
	%{buildroot}/srv/www/%{name}/tests \
	%{buildroot}/srv/www/%{name}/node_modules
rm -f %{buildroot}/srv/www/%{name}/.env

find %{buildroot}/srv/www/%{name} -type d -exec chmod 0755 {} \;
find %{buildroot}/srv/www/%{name} -type f -exec chmod 0644 {} \;
chmod 0755 %{buildroot}/srv/www/%{name}/artisan

install -d %{buildroot}/srv/www/%{name}/storage/framework/cache/data
install -d %{buildroot}/srv/www/%{name}/storage/framework/sessions
install -d %{buildroot}/srv/www/%{name}/storage/framework/views
install -d %{buildroot}/srv/www/%{name}/storage/logs
install -d %{buildroot}/srv/www/%{name}/bootstrap/cache

install -d %{buildroot}%{_sysconfdir}/sysconfig
install -m 0640 %{SOURCE3} %{buildroot}%{_sysconfdir}/sysconfig/akaunting
ln -s %{_sysconfdir}/sysconfig/akaunting %{buildroot}/srv/www/%{name}/.env

install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/akaunting << 'EOF'
#!/bin/sh
cd /srv/www/akaunting || exit 1
exec /usr/bin/php artisan "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/akaunting

install -d %{buildroot}%{_sysconfdir}/php-fpm-instances.d
cat > %{buildroot}%{_sysconfdir}/php-fpm-instances.d/akaunting.conf << 'EOF'
[global]
error_log = syslog

[akaunting]
user = www
group = www
listen = /run/php-fpm/akaunting.sock
listen.owner = www
listen.group = www
listen.mode = 0660

pm = dynamic
pm.max_children = 20
pm.start_servers = 2
pm.min_spare_servers = 1
pm.max_spare_servers = 5
pm.max_requests = 500

php_admin_value[memory_limit] = 512M
php_admin_value[upload_max_filesize] = 32M
php_admin_value[post_max_size] = 32M
php_admin_value[max_execution_time] = 120
php_admin_value[expose_php] = off
EOF

install -d %{buildroot}%{_sysconfdir}/nginx/sites-available
cat > %{buildroot}%{_sysconfdir}/nginx/sites-available/akaunting.conf << 'EOF'
upstream phpakaunting {
	server unix:/run/php-fpm/akaunting.sock;
}

server {
	listen 80;
	server_name akaunting.*;

	root /srv/www/akaunting;
	index index.php;

	client_max_body_size 32m;

	location / {
		try_files $uri $uri/ /index.php?$query_string;
	}

	location ~ \.php$ {
		fastcgi_pass phpakaunting;
		include fastcgi_params;
		fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
		fastcgi_param HTTPS $https if_not_empty;
	}

	location ~ /\.(?!well-known).* {
		deny all;
	}

	location ~ ^/(app|bootstrap|config|database|overrides|resources|routes|storage|tests)/ {
		deny all;
	}
}
EOF

install -d %{buildroot}%{_sysconfdir}/httpd/conf/webapps.d
cat > %{buildroot}%{_sysconfdir}/httpd/conf/webapps.d/akaunting.conf << 'EOF'
<Directory /srv/www/akaunting>
	AllowOverride None
	Require all granted
	DirectoryIndex index.php
	RewriteEngine On
	RewriteCond %{REQUEST_FILENAME} !-f
	RewriteCond %{REQUEST_FILENAME} !-d
	RewriteRule ^ index.php [L]
	<FilesMatch \.php$>
		SetHandler "proxy:unix:/run/php-fpm/akaunting.sock|fcgi://localhost"
	</FilesMatch>
</Directory>
EOF

install -d %{buildroot}%{_unitdir}
cat > %{buildroot}%{_unitdir}/akaunting-scheduler.service << 'EOF'
[Unit]
Description=Akaunting scheduler run
After=network.target mariadb.service

[Service]
Type=oneshot
User=www
Group=www
WorkingDirectory=/srv/www/akaunting
ExecStart=/usr/bin/php artisan schedule:run
EOF

cat > %{buildroot}%{_unitdir}/akaunting-scheduler.timer << 'EOF'
[Unit]
Description=Run the Akaunting scheduler every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=15s
Unit=akaunting-scheduler.service

[Install]
WantedBy=timers.target
EOF

install -d %{buildroot}%{_tmpfilesdir}
cat > %{buildroot}%{_tmpfilesdir}/akaunting.conf << 'EOF'
d /run/php-fpm 0755 www www -
EOF

%post
chown -R www:www /srv/www/akaunting/storage /srv/www/akaunting/bootstrap/cache
chmod -R u+rwX,g+rwX /srv/www/akaunting/storage /srv/www/akaunting/bootstrap/cache

%preun
if [ "$1" = 0 ]; then
	systemctl disable --now akaunting-scheduler.timer php-fpm@akaunting >/dev/null 2>&1 || :
fi

%files
%doc README.install.omv LICENSE.txt README.md
%{_bindir}/akaunting
%{_unitdir}/akaunting-scheduler.service
%{_unitdir}/akaunting-scheduler.timer
%config(noreplace) %{_sysconfdir}/php-fpm-instances.d/akaunting.conf
%{_tmpfilesdir}/akaunting.conf
%attr(0640,root,www) %config(noreplace) %{_sysconfdir}/sysconfig/akaunting
/srv/www/%{name}

%files nginx
%config(noreplace) %{_sysconfdir}/nginx/sites-available/akaunting.conf

%files apache
%config(noreplace) %{_sysconfdir}/httpd/conf/webapps.d/akaunting.conf
