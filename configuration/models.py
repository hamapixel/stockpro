from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models


class CompanySettings(models.Model):
    class HeaderMode(models.TextChoices):
        GENERATED = "generated", "Entête générée automatiquement"
        IMAGE = "image", "Image d’entête personnalisée"

    company_name = models.CharField(
        "Nom de la société",
        max_length=180,
        default="MSF - SARL",
    )
    legal_name = models.CharField(
        "Raison sociale",
        max_length=220,
        blank=True,
        default="MSF - SARL",
    )
    activity = models.CharField(
        "Activité",
        max_length=255,
        blank=True,
        default=(
            "Électricité, sanitaire, plomberie, peinture, "
            "cuisine et divers"
        ),
    )
    slogan = models.CharField(
        "Slogan",
        max_length=255,
        blank=True,
    )

    address = models.TextField(
        "Adresse",
        blank=True,
        default=(
            "N'Golonina, non loin de la mosquée de NIMAGA"
        ),
    )
    phone = models.CharField(
        "Téléphone principal",
        max_length=120,
        blank=True,
        default=(
            "+223 76 84 79 79 / 70 70 65 77 / "
            "75 75 19 58 / 79 30 43 81"
        ),
    )
    phone_secondary = models.CharField(
        "Téléphone secondaire",
        max_length=120,
        blank=True,
    )
    email = models.EmailField(
        "Adresse e-mail",
        blank=True,
    )
    website = models.CharField(
        "Site web",
        max_length=180,
        blank=True,
    )

    rccm = models.CharField(
        "RCCM",
        max_length=120,
        blank=True,
    )
    nif = models.CharField(
        "NIF",
        max_length=120,
        blank=True,
    )
    bank_details = models.TextField(
        "Coordonnées bancaires",
        blank=True,
    )

    logo = models.ImageField(
        "Logo de la société",
        upload_to="company/logo/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                ]
            )
        ],
    )

    invoice_header_mode = models.CharField(
        "Type d’entête des factures",
        max_length=20,
        choices=HeaderMode.choices,
        default=HeaderMode.IMAGE,
    )
    invoice_header = models.ImageField(
        "Image d’entête personnalisée",
        upload_to="company/invoice_headers/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                ]
            )
        ],
    )
    invoice_header_height_mm = models.PositiveSmallIntegerField(
        "Hauteur de l’entête",
        default=44,
        validators=[
            MinValueValidator(20),
            MaxValueValidator(80),
        ],
        help_text="Valeur recommandée : entre 35 et 50 mm.",
    )

    show_logo_on_generated_header = models.BooleanField(
        "Afficher le logo sur l’entête automatique",
        default=True,
    )
    invoice_footer_text = models.TextField(
        "Texte de pied de facture",
        blank=True,
        default="Merci pour votre confiance.",
    )
    invoice_terms = models.TextField(
        "Conditions ou observations",
        blank=True,
        default=(
            "Les marchandises vendues ne sont ni reprises ni "
            "échangées sauf accord préalable."
        ),
    )
    currency_label = models.CharField(
        "Devise affichée",
        max_length=30,
        default="F CFA",
    )

    updated_at = models.DateTimeField(
        "Dernière modification",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Paramètre de la société"
        verbose_name_plural = "Paramètres de la société"

    def __str__(self):
        return self.company_name

    def save(self, *args, **kwargs):
        # Cette table fonctionne comme un singleton : une seule ligne.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Les paramètres ne doivent pas être supprimés.
        return

    @classmethod
    def get_solo(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance