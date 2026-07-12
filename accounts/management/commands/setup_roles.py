from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from accounts.decorators import ADMIN_GROUP, SELLER_GROUP


class Command(BaseCommand):
    help = "Créer les groupes Administrateur et Vendeur."

    def handle(self, *args, **options):
        admin_group, _ = Group.objects.get_or_create(name=ADMIN_GROUP)
        seller_group, _ = Group.objects.get_or_create(name=SELLER_GROUP)

        User = get_user_model()

        superusers = User.objects.filter(is_superuser=True)

        for user in superusers:
            user.groups.add(admin_group)

        self.stdout.write(self.style.SUCCESS("Groupes créés avec succès."))
        self.stdout.write(self.style.SUCCESS("Superusers ajoutés au groupe Administrateur."))
        self.stdout.write("")
        self.stdout.write("Groupes disponibles :")
        self.stdout.write(f"- {ADMIN_GROUP}")
        self.stdout.write(f"- {SELLER_GROUP}")