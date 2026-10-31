#!/usr/bin/env python
# scripts/init_ad_test_data.py

"""
Создание тестовых пользователей и групп в AD (Samba AD DC).

Запускается после поднятия Samba AD DC:
    docker-compose -f docker-compose.ad.yml up -d
    python scripts/init_ad_test_data.py
"""

import subprocess
import time

import ldap3

AD_SERVER = "localhost"
AD_PORT = 389
AD_DOMAIN = "SAMDOM"
AD_USER = "administrator"
AD_PASSWORD = "Passw0rd"
SAMBA_CONTAINER = "dcap-ad-dc"


def set_password_samba_tool(username: str, password: str) -> bool:
    """Установить пароль через samba-tool внутри контейнера AD DC.

    ldap3.extend.microsoft.modify_password на Samba AD DC пароль не применяет
    (операция завершается успешно, но пароль не меняется), поэтому используем
    штатный samba-tool user setpassword. Возвращает True при успехе.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                SAMBA_CONTAINER,
                "samba-tool",
                "user",
                "setpassword",
                username,
                "--newpassword",
                password,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception:
        return False


def create_test_data():
    """Создание тестовых пользователей и групп"""
    server = ldap3.Server(AD_SERVER, port=AD_PORT, get_info=ldap3.ALL)
    conn = ldap3.Connection(
        server,
        user=f"{AD_USER}@{AD_DOMAIN}.EXAMPLE.COM",
        password=AD_PASSWORD,
        authentication=ldap3.SIMPLE,
        auto_bind=True,
    )

    base_dn = "DC=SAMDOM,DC=EXAMPLE,DC=COM"
    users_dn = f"CN=Users,{base_dn}"

    # 1. Создание групп
    groups = [
        ("DCAP_Admins", "Администраторы DCAP"),
        ("DCAP_Auditors", "Аудиторы DCAP"),
        ("DCAP_Scanners", "Сканеры DCAP"),
    ]

    for group_name, description in groups:
        group_dn = f"CN={group_name},{users_dn}"
        conn.add(
            group_dn,
            object_class=["top", "group"],
            attributes={
                "cn": group_name,
                "description": description,
                "sAMAccountName": group_name,
                "groupType": "2147483650",  # Global Security Group
            },
        )
        print(f"Created group: {group_name}")

    # 2. Создание пользователей
    users = [
        ("v.petrov", "Петров Василий", "Passw0rd"),
        ("a.smirnov", "Смирнов Алексей", "Passw0rd"),
        ("s.petrov", "Петров Сергей", "Passw0rd"),
        ("e.nikolaev", "Николаев Евгений", "Passw0rd"),
    ]

    for username, full_name, password in users:
        user_dn = f"CN={full_name},{users_dn}"
        parts = full_name.split()
        conn.add(
            user_dn,
            object_class=["top", "person", "organizationalPerson", "user"],
            attributes={
                "cn": full_name,
                "sn": parts[1] if len(parts) > 1 else full_name,
                "givenName": parts[0],
                "displayName": full_name,
                "sAMAccountName": username,
                "userPrincipalName": f"{username}@SAMDOM.EXAMPLE.COM",
                "userPassword": password,
            },
        )
        # Устанавливаем пароль (отдельная операция).
        # samba-tool внутри контейнера — основной способ; мой фолбэк — modify_password.
        if not set_password_samba_tool(username, password):
            conn.extend.microsoft.modify_password(user_dn, password)
        # Включаем учетную запись
        conn.modify(user_dn, {"userAccountControl": [(ldap3.MODIFY_REPLACE, 512)]})
        print(f"Created user: {username} ({full_name})")

    # 3. Добавление пользователей в группы
    group_members = {
        "DCAP_Admins": ["v.petrov"],
        "DCAP_Auditors": ["a.smirnov", "e.nikolaev"],
        "DCAP_Scanners": ["s.petrov"],
    }

    # Маппинг username → CN (мы создавали пользователей с CN=<полное имя>)
    username_cn = {u[0]: u[1] for u in users}

    for group_name, members in group_members.items():
        group_dn = f"CN={group_name},{users_dn}"
        for username in members:
            user_dn = f"CN={username_cn[username]},{users_dn}"
            conn.modify(group_dn, {"member": [(ldap3.MODIFY_ADD, [user_dn])]})
            print(f"Added {username} to {group_name}")

    print("\nTest data created successfully!")
    print("=" * 50)
    print("AD Users:")
    print("  v.petrov / Passw0rd (DCAP_Admins)")
    print("  a.smirnov / Passw0rd (DCAP_Auditors)")
    print("  s.petrov / Passw0rd (DCAP_Scanners)")
    print("  e.nikolaev / Passw0rd (DCAP_Auditors)")
    print("=" * 50)

    conn.unbind()


if __name__ == "__main__":
    time.sleep(10)
    create_test_data()