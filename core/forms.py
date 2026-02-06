from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm

# Import model-model baru
from .models import Kios, KiosAllocation, Armada, FertilizerPrice, Kecamatan, JenisPupuk, CompanyProfile, Kabupaten, UserProfile

# ==========================================
# FORM KIOS (Update: district -> kecamatan)
# ==========================================
class KiosForm(forms.ModelForm):
    class Meta:
        model = Kios
        # Perhatikan: 'district' diganti 'kecamatan'
        fields = ['name', 'pic_name', 'phone', 'kecamatan', 'address', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Kios'}),
            'pic_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Penanggung Jawab'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08xxx'}),
            'kecamatan': forms.Select(attrs={'class': 'form-select'}), # Dropdown otomatis dari Master Kecamatan
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ==========================================
# FORMSET ALOKASI (Update: fertilizer_type -> jenis_pupuk)
# ==========================================
KiosAllocationFormSet = inlineformset_factory(
    Kios, KiosAllocation,
    # Perhatikan: 'fertilizer_type' diganti 'jenis_pupuk'
    fields=('jenis_pupuk', 'year', 'quota_original'),
    extra=1, # Default 1 baris kosong
    can_delete=True,
    widgets={
        'jenis_pupuk': forms.Select(attrs={'class': 'form-select'}),
        'year': forms.NumberInput(attrs={'class': 'form-control'}),
        'quota_original': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ton'}),
    }
)

# ==========================================
# FORM ARMADA (Update: photo_url -> image upload)
# ==========================================
class ArmadaForm(forms.ModelForm):
    class Meta:
        model = Armada
        fields = ['plate_number', 'vehicle_type', 'driver_name', 'photo_url', 'is_active']
        widgets = {
            'plate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: Truk Engkel'}),
            'driver_name': forms.TextInput(attrs={'class': 'form-control'}),
            'photo_url': forms.FileInput(attrs={'class': 'form-control'}), # Ganti jadi FileInput
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ==========================================
# FORM HARGA (Hanya edit harga, jenis pupuk read-only di view)
# ==========================================
class HargaPupukForm(forms.ModelForm):
    class Meta:
        model = FertilizerPrice
        fields = ['kabupaten', 'price_buy', 'price_sell']
        widgets = {
            'kabupaten': forms.HiddenInput(),
            'price_buy': forms.TextInput(attrs={'class': 'form-control currency-input', 'inputmode': 'decimal', 'placeholder': '0'}),
            'price_sell': forms.TextInput(attrs={'class': 'form-control currency-input', 'inputmode': 'decimal', 'placeholder': '0'}),
        }

    def clean(self):
        cleaned = super().clean()
        pb = cleaned.get('price_buy') or 0
        ps = cleaned.get('price_sell') or 0
        if pb <= 0 or ps <= 0:
            raise forms.ValidationError('Harga beli/jual harus lebih dari 0.')
        return cleaned


# ==========================================
# FORM JENIS PUPUK (CRUD dinamis)
# ==========================================
class JenisPupukForm(forms.ModelForm):
    class Meta:
        model = JenisPupuk
        fields = ['name', 'code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Pupuk'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kode (unik)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ==========================================
# FORM COMPANY PROFILE (Singleton)
# ==========================================
class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ['name', 'address', 'phone', 'email', 'logo', 'bank_name', 'bank_account']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }


# ==========================================
# FORM KECAMATAN (Master Wilayah)
# ==========================================
class KecamatanForm(forms.ModelForm):
    class Meta:
        model = Kecamatan
        fields = ['name', 'code', 'kabupaten']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Kecamatan'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kode (opsional)'}),
            'kabupaten': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hanya tampilkan kabupaten aktif, kecuali saat edit (tetap tampilkan kabupaten yang sudah dipilih)
        qs = Kabupaten.objects.filter(is_active=True)
        if self.instance and self.instance.pk and self.instance.kabupaten_id:
            qs = qs | Kabupaten.objects.filter(pk=self.instance.kabupaten_id)
        self.fields['kabupaten'].queryset = qs.distinct().order_by('name')


# ==========================================
# FORM KABUPATEN
# ==========================================
class KabupatenForm(forms.ModelForm):
    class Meta:
        model = Kabupaten
        fields = ['name', 'code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Kabupaten'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kode (opsional)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ==========================================
# FORM USER MANAGEMENT (Admin creates staff)
# ==========================================
User = get_user_model()


class UserCreateForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=(
            ('admin', 'Admin (akses luas, bukan superuser)'),
            ('staff', 'Staff (akses terbatas)'),
        ),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Peran',
    )

    kabupaten = forms.ModelChoiceField(
        queryset=Kabupaten.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Kabupaten',
        help_text='Wajib untuk non-superuser; kosongkan hanya untuk superuser.',
    )

    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='Ulangi Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Password tidak sama.')
        kabupaten = cleaned.get('kabupaten')
        if not self.instance.is_superuser and not kabupaten:
            raise forms.ValidationError('Kabupaten wajib diisi untuk admin/staff.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = False
        if commit:
            user.set_password(self.cleaned_data['password1'])
            user.save()
            self._assign_group(user)
            self._assign_kabupaten(user)
        return user

    def _assign_group(self, user):
        from django.contrib.auth.models import Group
        role = self.cleaned_data.get('role')
        group_name = 'Admin' if role == 'admin' else 'Staff'
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.clear()
        user.groups.add(group)

    def _assign_kabupaten(self, user):
        kab = self.cleaned_data.get('kabupaten')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.kabupaten = kab
        profile.save(update_fields=['kabupaten'])


class UserSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


# ==========================================
# FORM USER EDIT (Update role, kabupaten, status)
# ==========================================
class UserEditForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=(
            ('admin', 'Admin (akses luas, bukan superuser)'),
            ('staff', 'Staff (akses terbatas)'),
        ),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Peran',
    )

    kabupaten = forms.ModelChoiceField(
        queryset=Kabupaten.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Kabupaten',
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Jika user sudah punya kabupaten yang nonaktif, tetap tampilkan
        if self.instance and self.instance.pk:
            profile = getattr(self.instance, 'profile', None)
            if profile and profile.kabupaten_id:
                qs = Kabupaten.objects.filter(is_active=True) | Kabupaten.objects.filter(pk=profile.kabupaten_id)
                self.fields['kabupaten'].queryset = qs.distinct().order_by('name')

    def clean(self):
        cleaned = super().clean()
        kabupaten = cleaned.get('kabupaten')
        if not kabupaten:
            raise forms.ValidationError('Kabupaten wajib diisi.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = False
        if commit:
            user.save()
            self._assign_group(user)
            self._assign_kabupaten(user)
        return user

    def _assign_group(self, user):
        from django.contrib.auth.models import Group
        role = self.cleaned_data.get('role')
        group_name = 'Admin' if role == 'admin' else 'Staff'
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.clear()
        user.groups.add(group)

    def _assign_kabupaten(self, user):
        kab = self.cleaned_data.get('kabupaten')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.kabupaten = kab
        profile.save(update_fields=['kabupaten'])