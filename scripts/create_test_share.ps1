# scripts/create_test_share.ps1
# (для Windows, если используется Windows VM)
#
# Создание тестовой папки с NTFS-правами для AD-тестов.

# Создание тестовой папки
New-Item -Path "C:\TestShare" -ItemType Directory -Force

# Создание подпапок
New-Item -Path "C:\TestShare\Data" -ItemType Directory -Force
New-Item -Path "C:\TestShare\Reports" -ItemType Directory -Force
New-Item -Path "C:\TestShare\Confidential" -ItemType Directory -Force

# Настройка NTFS прав
# Data — все читают/пишут
icacls "C:\TestShare\Data" /grant "SAMDOM\Domain Users:(OI)(CI)R,W"

# Reports — только аудиторы читают
icacls "C:\TestShare\Reports" /grant "SAMDOM\DCAP_Auditors:(OI)(CI)R"
icacls "C:\TestShare\Reports" /grant "SAMDOM\DCAP_Admins:(OI)(CI)F"

# Confidential — только администраторы
icacls "C:\TestShare\Confidential" /grant "SAMDOM\DCAP_Admins:(OI)(CI)F"
icacls "C:\TestShare\Confidential" /deny "SAMDOM\Domain Users:(R,W,D)"

# Создание общей папки (SMB)
New-SmbShare -Name "TestShare" -Path "C:\TestShare" -FullAccess "SAMDOM\Domain Users"