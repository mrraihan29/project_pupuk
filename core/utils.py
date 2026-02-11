from typing import Optional
from django.db.models import QuerySet
from django.contrib.auth import get_user_model
from .models import Kabupaten, JenisPupuk, FertilizerPrice, CompanyProfile

User = get_user_model()


def get_user_kabupaten(user: User):
    """Return kabupaten assigned to user via profile (None for superuser or unassigned)."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return None
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'kabupaten', None)


def get_scope_kabupaten(request) -> Optional[Kabupaten]:
    """
    Resolve kabupaten for current request:
    - Non-superuser: always user's kabupaten.
    - Superuser: optional GET ?kabupaten=<id>; otherwise None (all).
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None
    if not user.is_superuser:
        return get_user_kabupaten(user)
    kab_id = request.GET.get('kabupaten')
    if kab_id:
        try:
            return Kabupaten.objects.filter(pk=kab_id, is_active=True).first()
        except Exception:
            return None
    return None


def scope_by_kabupaten(qs: QuerySet, user: User, kabupaten_field: str = 'kabupaten') -> QuerySet:
    """
    Restrict queryset to user's kabupaten if applicable.
    kabupaten_field: dotted lookup string pointing to kabupaten on the target model (e.g., 'kecamatan__kabupaten').
    Superusers are not restricted.
    """
    if not qs or not user or not user.is_authenticated or user.is_superuser:
        return qs
    kab = get_user_kabupaten(user)
    if not kab:
        return qs
    return qs.filter(**{kabupaten_field: kab})


def get_price_for(jenis_pupuk: JenisPupuk, kabupaten: Optional[Kabupaten]):
    """
    Ambil harga untuk jenis pupuk dan kabupaten tertentu.
    Harus ada kabupaten; tanpa kabupaten akan None.
    """
    if not jenis_pupuk:
        return None
    if not kabupaten:
        return None
    return FertilizerPrice.objects.filter(jenis_pupuk=jenis_pupuk, kabupaten=kabupaten).first()


def get_price_by_code(jenis_code: str, kabupaten: Optional[Kabupaten]):
    try:
        jenis = JenisPupuk.objects.get(code=jenis_code)
    except JenisPupuk.DoesNotExist:
        return None
    return get_price_for(jenis, kabupaten)


def get_company_profile(kabupaten: Optional[Kabupaten] = None) -> Optional[CompanyProfile]:
    """
    Resolve CompanyProfile for a given kabupaten with fallback to default.
    Priority: kabupaten-specific profile → default profile (kabupaten=None) → None.
    """
    if kabupaten:
        profile = CompanyProfile.objects.filter(kabupaten=kabupaten).first()
        if profile:
            return profile
    # Fallback: profil default (kabupaten=NULL) atau profil pertama yang ada
    return CompanyProfile.objects.filter(kabupaten__isnull=True).first() or CompanyProfile.objects.first()
