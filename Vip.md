#profile-title: base64:4pisU0jOntCvVklO4oSiIHwgVmlwIHR1bm5lbA==
#profile-update-interval: 1
#subscription-userinfo: upload=29; download=18; total=937418240000000; expire=2546249531
#profile-web-page-url: hiddifynext.page.dev
#profile-title: base64:4pisU0jOntCvVklO4oSiIHwgVmlwIHR1bm5lbA==
#profile-update-interval: 1
#subscription-userinfo: upload=29; download=18; total=937418240000000; expire=2546249531
#support-url: t.me/shervini
vless://853d23ee-38c6-41bb-a51c-8aea6a25b0bd@tes1.api-tel.xyz:50855?encryption=none&flow=&fp=chrome&pbk=3iQ5QX52pIjouDXoPSfrQRvpqaOTqG26IJLctU7McAY&security=reality&sid=02&sni=ea.com&type=#%E2%98%ACSH%CE%9EN%E2%84%A2%20%E2%9C%A8%20Quantum%20
vless://853d23ee-38c6-41bb-a51c-8aea6a25b0bd@tes1.api-tel.xyz:50855?encryption=none&flow=&fp=chrome&pbk=3iQ5QX52pIjouDXoPSfrQRvpqaOTqG26IJLctU7McAY&security=reality&sid=02&sni=ea.com&type=#%E2%98%ACSH%CE%9EN%E2%84%A2%20%E2%9C%A8%20Quantum%20
vless://853d23ee-38c6-41bb-a51c-8aea6a25b0bd@tes1.api-tel.xyz:50855?encryption=none&flow=&fp=chrome&pbk=3iQ5QX52pIjouDXoPSfrQRvpqaOTqG26IJLctU7McAY&security=reality&sid=02&sni=ea.com&type=#%E2%98%ACSH%CE%9EN%E2%84%A2%20%E2%9C%A8%20Quantum%20
vless://853d23ee-38c6-41bb-a51c-8aea6a25b0bd@tes1.api-tel.xyz:50855?encryption=none&flow=&fp=chrome&pbk=3iQ5QX52pIjouDXoPSfrQRvpqaOTqG26IJLctU7McAY&security=reality&sid=02&sni=ea.com&type=#%E2%98%ACSH%CE%9EN%E2%84%A2%20%E2%9C%A8%20Quantum%20
vless://853d23ee-38c6-41bb-a51c-8aea6a25b0bd@tes1.api-tel.xyz:50855?encryption=none&flow=&fp=chrome&pbk=3iQ5QX52pIjouDXoPSfrQRvpqaOTqG26IJLctU7McAY&security=reality&sid=02&sni=ea.com&type=#%E2%98%ACSH%CE%9EN%E2%84%A2%20%E2%9C%A8%20Quantum%20
vless://853d23ee-38c6-41bb-a51c-8aea6a25b0bd@tes1.api-tel.xyz:50855?encryption=none&flow=&fp=chrome&pbk=3iQ5QX52pIjouDXoPSfrQRvpqaOTqG26IJLctU7McAY&security=reality&sid=02&sni=ea.com&type=#%E2%98%ACSH%CE%9EN%E2%84%A2%20%E2%9C%A8%20Quantum%20
{
  "dns": {
    "final": "dns-remote",
    "independent_cache": true,
    "rules": [
      {
        "domain": [
          "tes1.api-tel.xyz",
          "dns.google"
        ],
        "server": "dns-direct"
      },
      {
        "action": "reject",
        "clash_mode": "block"
      },
      {
        "clash_mode": "direct",
        "server": "dns-direct"
      },
      {
        "clash_mode": "global",
        "server": "dns-remote"
      },
      {
        "disable_cache": true,
        "inbound": [
          "tun-in"
        ],
        "query_type": [
          "A",
          "AAAA"
        ],
        "server": "dns-fake"
      }
    ],
    "servers": [
      {
        "detour": "☬SHΞN™ ✨ Quantum ",
        "domain_resolver": {
          "server": "dns-direct"
        },
        "server": "dns.google",
        "tag": "dns-remote",
        "type": "tcp"
      },
      {
        "tag": "dns-direct",
        "type": "local"
      },
      {
        "tag": "dns-local",
        "type": "local"
      },
      {
        "inet4_range": "198.51.100.0/24",
        "inet6_range": "2001:2::/48",
        "tag": "dns-fake",
        "type": "fakeip"
      }
    ]
  },
  "experimental": {
    "cache_file": {
      "enabled": true,
      "path": "../cache/cache.db",
      "store_fakeip": true
    }
  },
  "inbounds": [
    {
      "address": [
        "172.19.0.1/28",
        "fdfe:dcba:9876::1/126"
      ],
      "mtu": 9000,
      "stack": "mixed",
      "tag": "tun-in",
      "type": "tun"
    },
    {
      "listen": "0.0.0.0",
      "listen_port": 2080,
      "tag": "mixed-in",
      "type": "mixed"
    }
  ],
  "log": {
    "level": "panic"
  },
  "outbounds": [
    {
      "server": "tes1.api-tel.xyz",
      "server_port": 50855,
      "tls": {
        "enabled": true,
        "reality": {
          "enabled": true,
          "public_key": "3iQ5QX52pIjouDXoPSfrQRvpqaOTqG26IJLctU7McAY",
          "short_id": "02"
        },
        "server_name": "ea.com",
        "utls": {
          "enabled": true,
          "fingerprint": "chrome"
        }
      },
      "uuid": "853d23ee-38c6-41bb-a51c-8aea6a25b0bd",
      "type": "vless",
      "network_type": [
        "cellular"
      ],
      "network_strategy": "default",
      "domain_resolver": {
        "server": "dns-direct"
      },
      "tag": "☬SHΞN™ ✨ Quantum "
    },
    {
      "domain_resolver": {
        "server": "dns-direct"
      },
      "network_strategy": "default",
      "network_type": [
        "cellular"
      ],
      "tag": "direct",
      "type": "direct"
    },
    {
      "tag": "block",
      "type": "block"
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "final": "☬SHΞN™ ✨ Quantum ",
    "rules": [
      {
        "action": "hijack-dns",
        "ip_cidr": [
          "172.19.0.2",
          "fdfe:dcba:9876::2"
        ]
      },
      {
        "action": "reject",
        "clash_mode": "block"
      },
      {
        "clash_mode": "direct",
        "outbound": "direct"
      },
      {
        "clash_mode": "global",
        "outbound": "☬SHΞN™ ✨ Quantum "
      },
      {
        "action": "sniff"
      },
      {
        "action": "hijack-dns",
        "protocol": [
          "dns"
        ]
      },
      {
        "action": "route",
        "network": [
          "icmp"
        ],
        "outbound": "direct"
      }
    ]
  }
}
