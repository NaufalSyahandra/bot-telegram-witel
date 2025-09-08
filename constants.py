from enum import Enum
from telegram import ReplyKeyboardMarkup


class UserState(Enum):
    """User state enumeration"""
    UNREGISTERED = "unregistered"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"
    IDLE = "idle"
    WAITING_INPUT = "waiting_input"
    KENDALA_MENU = "kendala_menu"
    TEKNIK_SUBMENU = "teknik_submenu"
    TAT_SUBMENU = "tat_submenu"  # NEW: Added TAT submenu state
    PELANGGAN_SUBMENU = "pelanggan_submenu"
    WAITING_MEDIA = "waiting_media"
    ADMIN_MENU = "admin_menu"
    WAITING_ADMIN_NIK = "waiting_admin_nik"


class KendalaType(Enum):
    """Kendala type enumeration"""
    TAJ = "taj"  # Tidak ada Jaringan
    TAT_BELUM_ACC = "tat_belum_acc"  # TAT Belum ACC Tiang (original TAT)
    TAT_SUDAH_ACC = "tat_sudah_acc"  # TAT Sudah ACC Tiang (new)
    ODP_FULL = "odp_full"
    PELANGGAN_MANJA = "pelanggan_manja"
    PELANGGAN_CANCEL = "pelanggan_cancel"
    CABUT_PASANG = "cabut_pasang"
    LAINNYA = "lainnya"


class UserRole(Enum):
    """User role enumeration"""
    OWNER = "owner"
    ADMIN = "admin"
    EMPLOYEE = "employee"


class Messages:
    """Static messages for bot responses with enhanced user management"""

    WELCOME_UNREGISTERED = """👋 Selamat datang di Bot Test!

🔐 Untuk menggunakan bot ini, Anda harus mendaftar terlebih dahulu.

📝 Silakan kirim NIK Anda (6-8 digit) untuk pendaftaran."""

    REGISTRATION_SUCCESS = """✅ Pendaftaran berhasil!

⏳ NIK Anda sedang dalam proses verifikasi oleh admin.
Silakan tunggu konfirmasi untuk dapat mengakses fitur bot."""

    REGISTRATION_PENDING = """⏳ NIK Anda masih dalam proses verifikasi.

Silakan tunggu konfirmasi dari admin."""

    REGISTRATION_REJECTED = """❌ Pendaftaran Anda ditolak.

Silakan hubungi admin jika Anda merasa ini adalah kesalahan."""

    REGISTRATION_REJECTED_CAN_RETRY = """❌ Pendaftaran sebelumnya ditolak.

🔄 Anda dapat mendaftar ulang dengan mengirim NIK yang valid (6-8 digit).
📝 Pastikan NIK yang Anda kirim adalah NIK yang benar."""

    WELCOME_APPROVED = """👋 Selamat datang kembali!

✅ Akun Anda sudah diverifikasi.
📌 Pilih jenis kendala di bawah ini:"""

    ADMIN_WELCOME = """🔧 Menu Admin

Pilih aksi yang ingin dilakukan:"""

    OWNER_WELCOME = """👑 Menu Owner

Pilih aksi yang ingin dilakukan:"""

    INVALID_NIK = """❌ NIK tidak valid!

NIK harus berupa 6-8 digit angka. Silakan coba lagi."""

    NIK_ALREADY_REGISTERED = """⚠️ NIK sudah terdaftar!

Jika Anda lupa status pendaftaran, silakan hubungi admin."""

    ADMIN_APPROVAL_NOTIFICATION = """🔔 Pendaftaran Baru

NIK: {nik}
User ID: {user_id}
Username: @{username}

Pilih tindakan untuk pendaftaran ini:"""

    EMPLOYEE_APPROVED = """✅ Pendaftaran Disetujui!

NIK {nik} telah disetujui. Sekarang Anda dapat mengakses bot."""

    EMPLOYEE_REJECTED = """❌ Pendaftaran Ditolak!

NIK {nik} tidak dapat mengakses bot.
🔄 Anda dapat mendaftar ulang kapan saja dengan mengirim /start."""

    # New notification messages for owner
    OWNER_APPROVAL_NOTIFICATION = """📋 Notifikasi Persetujuan

✅ User dengan NIK {nik} telah DISETUJUI oleh {approver_role} {approver_nik}

👤 Detail User:
• NIK: {nik}
• User ID: {user_id}
• Username: @{username}
• Disetujui oleh: {approver_role} ({approver_nik})"""

    OWNER_REJECTION_NOTIFICATION = """📋 Notifikasi Penolakan

❌ User dengan NIK {nik} telah DITOLAK oleh {rejector_role} {rejector_nik}

👤 Detail User:
• NIK: {nik}
• User ID: {user_id}
• Username: @{username}
• Ditolak oleh: {rejector_role} ({rejector_nik})"""

    ADD_ADMIN_REQUEST = """➕ Tambah Admin Baru

Silakan kirim NIK admin yang akan ditambahkan (6-8 digit):

⚠️ Pastikan NIK sudah terdaftar sebagai user terlebih dahulu!"""

    ADMIN_ADDED = """✅ Admin berhasil ditambahkan!

NIK {nik} sekarang memiliki akses admin.
🔔 User tersebut akan menerima notifikasi."""

    ADMIN_ADD_ERROR = """❌ Gagal menambahkan admin!

Pastikan:
• NIK valid (6-8 digit)
• NIK sudah terdaftar sebagai user
• NIK belum menjadi admin"""

    UNAUTHORIZED = """🚫 Anda tidak memiliki akses untuk fitur ini.

Silakan daftar terlebih dahulu dengan mengirim NIK Anda."""

    KENDALA_MENU = """📋 Pilih jenis kendala:"""
    TEKNIK_SUBMENU = """🔧 Pilih kendala teknik:"""
    TAT_SUBMENU = """🏗️ Pilih jenis TAT (Tidak ada Tiang):"""  # NEW: TAT submenu message
    PELANGGAN_SUBMENU = """👤 Pilih kendala pelanggan:"""

    # Format TAJ - NIK removed from input
    TAJ_FORMAT = """📝 Silakan kirim data dengan format berikut:

Nama Pelanggan: John Doe
SC: 12345
STO: ABC
Tag Pelanggan: PEL-456
Detail Kendala: Tidak ada Jaringan (TAJ)

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format TAT Belum ACC - NIK removed from input (original TAT format)
    TAT_BELUM_ACC_FORMAT = """📝 Silakan kirim data dengan format berikut:

Nama Pelanggan: John Doe
SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
Tag Pelanggan: PEL-456
Jumlah Tiang: 5
Jarak Real: 20m
Detail Kendala: Tidak ada Tiang (TAT Belum ACC)
CP RT/RW/Developer: Pak RT 081234567890

⚠️ Pastikan semua field diisi dengan benar!"""

    # NEW: Format TAT Sudah ACC - simplified format without CP RT/RW/Developer
    TAT_SUDAH_ACC_FORMAT = """📝 Silakan kirim data dengan format berikut:

Nama Pelanggan: John Doe
SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
Tag Pelanggan: PEL-456
Jumlah Tiang: 5
Jarak Real: 20m
Detail Kendala: Tidak ada Tiang (TAT Sudah ACC)

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format ODP Full - NIK removed from input
    ODP_FULL_FORMAT = """📝 Silakan kirim data dengan format berikut:

Nama Pelanggan: John Doe
SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
ID Valins: VAL-123
Tag Pelanggan: PEL-456
Jarak Real: 20m
Detail Kendala: ODP Full

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format Pelanggan Manja - NIK removed from input
    PELANGGAN_MANJA_FORMAT = """📝 Silakan kirim data dengan format berikut:

Nama Pelanggan: John Doe
SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
ID Valins: VAL-123
Tag Pelanggan: PEL-456
Jarak Real: 20m
Detail Kendala: Pelanggan Manja
Tanggal (Manja): 2024-01-15

⚠️ Pastikan semua field diisi dengan benar!
📸 Eviden akan diupload sebagai foto di langkah selanjutnya."""

    # Format Pelanggan Cancel - NIK removed from input
    PELANGGAN_CANCEL_FORMAT = """📝 Silakan kirim data dengan format berikut:

Nama Pelanggan: John Doe
SC: 12345
STO: ABC
Alasan Cancel: Pelanggan tidak membutuhkan lagi
Detail Kendala: Pelanggan Cancel
Tanggal (Cancel): 2024-01-15

⚠️ Pastikan semua field diisi dengan benar!
📸 Eviden akan diupload sebagai foto di langkah selanjutnya."""

    # Format Cabut Pasang - NIK removed from input
    CABUT_PASANG_FORMAT = """📝 Silakan kirim data dengan format berikut:

Nama Pelanggan: John Doe
SC: 12345
STO: ABC
No Indihome Aktif: 123456789
Detail Kendala: Cabut Pasang

⚠️ Pastikan semua field diisi dengan benar!
📸 Eviden modem/jalur kabel akan diupload sebagai foto di langkah selanjutnya."""

    # Format Lainnya - NIK removed from input
    GENERAL_FORMAT = """📝 Silakan kirim data dengan format berikut:

Nama Pelanggan: John Doe
SC: 12345
STO: ABC
Tag Pelanggan: PEL-456
Detail Kendala: {kendala_type}

⚠️ Pastikan semua field diisi dengan benar!"""

    # Media prompts remain the same
    TAJ_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 🎥 Video kondisi rumah pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    TAT_BELUM_ACC_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 📸 Foto rencana pemasangan tiang
3. 📸 Bukti sudah menyerahkan file untuk sitac
4. 🎥 Video kondisi rumah pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    # NEW: TAT Sudah ACC media prompt - only one media required
    TAT_SUDAH_ACC_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Bukti sudah menyerahkan file untuk sitac

⚠️ Kirim foto sesuai permintaan!"""

    ODP_FULL_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 📸 Capture lensa nearest ODP dimana masih dalam range 250m

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    PELANGGAN_MANJA_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Eviden Manja (foto bukti)
2. 📸 Foto bukti WA / foto dengan pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    PELANGGAN_CANCEL_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Eviden Cancel (foto bukti)
2. 📸 Foto bukti WA / foto dengan pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    CABUT_PASANG_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Eviden modem/jalur kabel ke pelanggan
2. 📸 Foto bukti WA / foto dengan pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    LAINNYA_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto penjelasan kondisi kendala
2. 🎥 Video penjelasan kondisi kendala

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    GENERAL_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto Penjelasan kondisi kendala
2. 🎥 Video penjelasan kondisi kendala

⚠️ Kirim foto dan video sesuai permintaan!"""

    MEDIA_RECEIVED = """✅ Media diterima ({media_count} file)!

📸 Anda masih bisa mengirim foto/video lainnya, atau klik 'Selesai' jika sudah lengkap."""

    DATA_SAVED = "✅ Data berhasil disimpan ke Google Sheet!"
    MEDIA_SAVED = "✅ Media berhasil diupload! ({media_type})"
    MEDIA_ERROR = "❌ Gagal mengupload media. Silakan coba lagi."
    MEDIA_REQUIRED = "⚠️ Anda harus mengirim minimal 1 foto atau video sebelum menyelesaikan input data!"
    HELP_TEXT = "❓ Ketik /start untuk memulai ulang bot.\n\n📋 Bot ini membantu Anda menginput data SC ke Google Sheet dengan mudah."
    RATE_LIMIT = "⏳ Tunggu sebentar sebelum kirim data lagi."


class MenuKeyboards:
    """Static keyboard layouts with enhanced user management"""

    MAIN = [
        ["🔧 Kendala Teknik", "👤 Kendala Pelanggan"],
        ["❓ Kendala Lainnya", "🆘 Bantuan"]
    ]

    TEKNIK = [
        ["📶 Tidak ada Jaringan (TAJ)"],
        ["🏗️ Tidak ada Tiang (TAT)"],
        ["🔌 ODP Full"],
        ["🏠 Menu Utama"]
    ]

    # NEW: TAT submenu keyboard
    TAT = [
        ["✅ TAT Sudah ACC"],
        ["❌ TAT Belum ACC"],
        ["🏠 Menu Utama"]
    ]

    PELANGGAN = [
        ["😤 Pelanggan Manja"],
        ["❌ Pelanggan Cancel"],
        ["🔄 Cabut Pasang"],
        ["🏠 Menu Utama"]
    ]

    # Enhanced admin menu with user removal capability
    ADMIN = [
        ["📋 Lihat Pendaftar"],
        ["🗑️ Hapus User"],
        ["🏠 Menu Utama"]
    ]

    # Enhanced owner menu with user management
    OWNER = [
        ["📋 Lihat Pendaftar", "➕ Tambah Admin"],
        ["👥 Lihat Admin", "🗂️ Kelola User"],
        ["➖ Hapus Admin", "🗑️ Hapus User"],
        ["🏠 Menu Utama"]
    ]

    BACK = [["🏠 Menu Utama"]]

    MEDIA_OPTIONS = [
        ["✅ Selesai"],
        ["🏠 Menu Utama"]
    ]

    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.MAIN, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def teknik_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.TEKNIK, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def tat_menu():  # NEW: TAT submenu
        return ReplyKeyboardMarkup(MenuKeyboards.TAT, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def pelanggan_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.PELANGGAN, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def admin_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.ADMIN, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def owner_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.OWNER, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def back_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.BACK, resize_keyboard=True)

    @staticmethod
    def media_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.MEDIA_OPTIONS, resize_keyboard=True)


# Sheet configurations - updated to handle both TAT types
SHEET_CONFIGS = {
    "teknik": {
        "name": "Kendala Teknik",
        "columns": [
            "NIK", "Nama Pelanggan", "SC", "STO", "Detail Kendala", "Tag Pelanggan",
            "Nama ODP", "ID Valins", "Jarak Real", "Jumlah Tiang", "CP RT/RW/Developer",
            # Photo columns
            "Foto dengan Pelanggan/Foto Rumah Pelanggan",
            "Foto Rencana Pemasangan Tiang",
            "Bukti Sudah Menyerahkan File untuk Sitac",
            "Capture Lensa Nearest ODP dimana Masih dalam Range 250m",
            "Video Kondisi Rumah Pelanggan",
            "created_at"
        ]
    },
    "pelanggan": {
        "name": "Kendala Pelanggan",
        "columns": [
            "NIK", "Nama Pelanggan", "SC", "STO", "Detail Kendala",
            "Nama ODP", "ID Valins", "Tag Pelanggan", "Jarak Real",
            "No Indihome Aktif", "Eviden (Manja/Cancel)", "Tanggal (Manja)",
            "Tanggal (Cancel)", "Alasan Cancel",
            # Photo columns
            "Eviden Modem/Jalur Kabel ke Pelanggan",
            "Foto Bukti WA / Foto dengan Pelanggan",
            "created_at"
        ]
    },
    "lainnya": {
        "name": "Kendala Lainnya",
        "columns": [
            "NIK", "Nama Pelanggan", "SC", "STO", "Detail Kendala", "Tag Pelanggan",
            # Photo columns
            "Foto Penjelasan Kondisi Kendala",
            "Video Penjelasan Kondisi Kendala",
            "created_at"
        ]
    },
    # TAMBAHAN: Konfigurasi sheet untuk data user/teknisi
    "teknisi": {
        "name": "Teknisi",
        "columns": [
            "NIK", "User_ID", "Username", "Role", "Status", "Approved_By", "Approved_At", "Created_At"
        ]
    }
}

# Function to get sheet config based on kendala type
def get_sheet_config(kendala_type: KendalaType):
    """Get sheet configuration based on kendala type"""
    if kendala_type in [KendalaType.TAJ, KendalaType.TAT_BELUM_ACC, KendalaType.TAT_SUDAH_ACC, KendalaType.ODP_FULL]:
        return SHEET_CONFIGS["teknik"]
    elif kendala_type in [KendalaType.PELANGGAN_MANJA, KendalaType.PELANGGAN_CANCEL, KendalaType.CABUT_PASANG]:
        return SHEET_CONFIGS["pelanggan"]
    else:  # LAINNYA
        return SHEET_CONFIGS["lainnya"]

# Define which fields are required for each kendala type - UPDATED for TAT split
REQUIRED_FIELDS = {
    KendalaType.TAJ: ["Nama Pelanggan", "SC", "STO", "Tag Pelanggan", "Detail Kendala"],
    KendalaType.TAT_BELUM_ACC: ["Nama Pelanggan", "SC", "STO", "Nama ODP", "Tag Pelanggan", "Jumlah Tiang", "Jarak Real", "Detail Kendala", "CP RT/RW/Developer"],
    KendalaType.TAT_SUDAH_ACC: ["Nama Pelanggan", "SC", "STO", "Nama ODP", "Tag Pelanggan", "Jumlah Tiang", "Jarak Real", "Detail Kendala"],  # NEW: No CP RT/RW/Developer
    KendalaType.ODP_FULL: ["Nama Pelanggan", "SC", "STO", "Nama ODP", "ID Valins", "Tag Pelanggan", "Jarak Real", "Detail Kendala"],
    KendalaType.PELANGGAN_MANJA: ["Nama Pelanggan", "SC", "STO", "Nama ODP", "ID Valins", "Tag Pelanggan", "Jarak Real", "Detail Kendala", "Tanggal (Manja)"],
    KendalaType.PELANGGAN_CANCEL: ["Nama Pelanggan", "SC", "STO", "Alasan Cancel", "Detail Kendala", "Tanggal (Cancel)"],
    KendalaType.CABUT_PASANG: ["Nama Pelanggan", "SC", "STO", "No Indihome Aktif", "Detail Kendala"],
    KendalaType.LAINNYA: ["Nama Pelanggan", "SC", "STO", "Tag Pelanggan", "Detail Kendala"]
}

# Media fields with types - UPDATED for TAT split
MEDIA_FIELDS_WITH_TYPES = {
    KendalaType.TAJ: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Video Kondisi Rumah Pelanggan", "video", "🎥 Video kondisi rumah pelanggan"),
    ],
    KendalaType.TAT_BELUM_ACC: [  # Original TAT with all media
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Foto Rencana Pemasangan Tiang", "photo", "📸 Foto rencana pemasangan tiang"),
        ("Bukti Sudah Menyerahkan File untuk Sitac", "photo", "📸 Bukti sudah menyerahkan file untuk sitac"),
        ("Video Kondisi Rumah Pelanggan", "video", "🎥 Video kondisi rumah pelanggan"),
    ],
    KendalaType.TAT_SUDAH_ACC: [  # NEW: TAT ACC with only sitac file
        ("Bukti Sudah Menyerahkan File untuk Sitac", "photo", "📸 Bukti sudah menyerahkan file untuk sitac"),
    ],
    KendalaType.ODP_FULL: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Capture Lensa Nearest ODP dimana Masih dalam Range 250m", "photo", "📸 Capture lensa nearest ODP dimana masih dalam range 250m"),
    ],
    KendalaType.PELANGGAN_MANJA: [
        ("Eviden (Manja/Cancel)", "photo", "📸 Eviden Manja (foto bukti)"),
    ],
    KendalaType.PELANGGAN_CANCEL: [
        ("Eviden (Manja/Cancel)", "photo", "📸 Eviden Cancel (foto bukti)")
    ],
    KendalaType.CABUT_PASANG: [
        ("Eviden Modem/Jalur Kabel ke Pelanggan", "photo", "📸 Eviden modem/jalur kabel ke pelanggan"),
        ("Foto Bukti WA / Foto dengan Pelanggan", "photo", "📸 Foto bukti WA / foto dengan pelanggan"),
    ],
    KendalaType.LAINNYA: [
        ("Foto Penjelasan Kondisi Kendala", "photo", "📸 Foto penjelasan kondisi kendala"),
        ("Video Penjelasan Kondisi Kendala", "video", "🎥 Video penjelasan kondisi kendala")
    ]
}

# Legacy media fields (for backward compatibility)
MEDIA_FIELDS = {
    kendala_type: [item[0] for item in fields]
    for kendala_type, fields in MEDIA_FIELDS_WITH_TYPES.items()
}