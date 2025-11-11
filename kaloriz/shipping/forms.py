from django import forms
from .models import Address, District


class AddressForm(forms.ModelForm):
    """
    Form untuk alamat pengiriman dengan field standard
    """
    class Meta:
        model = Address
        fields = [
            'label', 'full_name', 'phone',
            'province', 'city', 'district', 'postal_code',
            'street_name', 'detail',
            'latitude', 'longitude',
            'is_default',
        ]
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: Rumah, Kantor, Apartemen'
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nama lengkap penerima'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '08123456789'
            }),
            'province': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly'
            }),
            'district': forms.Select(attrs={
                'class': 'form-control'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '90xxx'
            }),
            'street_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: Jl. A.P. Pettarani No. 123'
            }),
            'detail': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Detail tambahan: Blok, nomor rumah, patokan, warna cat, dll (opsional)'
            }),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'label': 'Label Alamat',
            'full_name': 'Nama Lengkap',
            'phone': 'Nomor Telepon',
            'province': 'Provinsi',
            'city': 'Kota',
            'district': 'Kecamatan',
            'postal_code': 'Kode Pos',
            'street_name': 'Nama Jalan',
            'detail': 'Detail Lainnya',
            'is_default': 'Jadikan alamat utama',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default province and city
        if not self.instance.pk:
            self.fields['province'].initial = 'Sulawesi Selatan'
            self.fields['city'].initial = 'Makassar'

        # Load active districts only
        self.fields['district'].queryset = District.objects.filter(is_active=True).order_by('name')

    def clean_phone(self):
        """
        Validasi nomor telepon Indonesia
        """
        phone = self.cleaned_data.get('phone')

        # Normalize phone number
        if phone:
            phone = phone.strip().replace(' ', '').replace('-', '')

            # Validate format
            if not phone.startswith(('08', '+62', '62')):
                raise forms.ValidationError(
                    'Nomor telepon harus dimulai dengan 08, +62, atau 62'
                )

            # Validate length
            if phone.startswith('08'):
                if len(phone) < 10 or len(phone) > 13:
                    raise forms.ValidationError(
                        'Nomor telepon tidak valid (harus 10-13 digit)'
                    )
            elif phone.startswith('+62'):
                if len(phone) < 12 or len(phone) > 15:
                    raise forms.ValidationError(
                        'Nomor telepon tidak valid'
                    )

        return phone

    def clean_postal_code(self):
        """
        Validasi kode pos Makassar (90xxx)
        """
        postal_code = self.cleaned_data.get('postal_code')

        if postal_code:
            # Remove any spaces
            postal_code = postal_code.strip()

            # Check if it's numeric
            if not postal_code.isdigit():
                raise forms.ValidationError('Kode pos harus berupa angka')

            # Check if it starts with 90 (Makassar)
            if not postal_code.startswith('90'):
                raise forms.ValidationError(
                    'Kode pos harus dimulai dengan 90 (Makassar)'
                )

            # Check length
            if len(postal_code) != 5:
                raise forms.ValidationError('Kode pos harus 5 digit')

        return postal_code
