"""Пакет коннекторов Manager (permissions, audit).

BUG-259: наличие __init__.py делает `connectors` regular-пакетом Manager'а.
Без него каталог остаётся namespace-portion, и при одновременном нахождении
на sys.path `scanner/connectors` (regular-пакет) перехватывает имя `connectors`
в combined-прогоне тестов.
"""
