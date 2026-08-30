# manager/src/db/init_roles.py
import logging
from sqlalchemy.orm import Session

from manager.src.auth.models import User, Role

logger = logging.getLogger(__name__)


def init_roles_and_admin(db: Session):
    """Инициализация ролей и создание admin (если не существует)."""

    # Создание ролей
    roles_data = [
        {"name": "admin", "description": "Full system access"},
        {"name": "auditor", "description": "Audit and read access"},
        {"name": "scanner", "description": "Scan execution access"},
        {"name": "viewer", "description": "Read-only access"},
    ]

    for role_data in roles_data:
        role = db.query(Role).filter(Role.name == role_data["name"]).first()
        if not role:
            role = Role(**role_data)
            db.add(role)
            logger.info(f"Created role: {role_data['name']}")

    db.commit()

    # Создание admin пользователя (если не существует)
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@dcap.local",
            full_name="Administrator",
            auth_source="local",
            is_active=True,
        )
        admin.set_password("admin123")  # Временный пароль
        logger.warning("=" * 60)
        logger.warning("ADMIN USER CREATED WITH DEFAULT PASSWORD")
        logger.warning("Username: admin")
        logger.warning("Password: admin123")
        logger.warning("CHANGE THIS PASSWORD IMMEDIATELY!")
        logger.warning("=" * 60)

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if admin_role:
            admin.roles.append(admin_role)

        db.add(admin)
        db.commit()
        logger.info("Created admin user")

    # Добавление роли viewer для всех существующих пользователей без ролей
    for user in db.query(User).filter(~User.roles.any()).all():
        viewer_role = db.query(Role).filter(Role.name == "viewer").first()
        if viewer_role:
            user.roles.append(viewer_role)

    db.commit()
