from enum import Enum
from telegram import ReplyKeyboardMarkup


class UserState(Enum):
    """User state enumeration"""
    IDLE = "idle"
    WAITING_INPUT = "waiting_input"
    KENDALA_MENU = "kendala_menu"
    TEKNIK_SUBMENU = "teknik_submenu"
    WAITING_MEDIA = "waiting_media"


class KendalaType(Enum):
    """Kendala type enumeration"""
    TAJ = "taj"  # Tidak ada Jaringan
    TAT = "tat"  # Tidak ada Tiang
    ODP_FULL = "odp_full"
    PELANGGAN = "pelanggan"
    LAINNYA = "lainnya"


class Messages:
    """Static messages for bot responses"""

    WELCOME = """👋 Halo! Selamat datang di Bot Test.

📌 Pilih jenis kendala di bawah ini:"""

    KENDALA_MENU = """📋 Pilih jenis kendala:"""
    TEKNIK_SUBMENU = """🔧 Pilih kendala teknik:"""

    # Format TAJ
    TAJ_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Tag Pelanggan: PEL-456
Detail Kendala: Tidak ada Jaringan (TAJ)

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format TAT
    TAT_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
ID Valins: VAL-123
Tag Pelanggan: PEL-456
Jumlah Tiang: 5
Jarak: 20m
Detail Kendala: Tidak ada Tiang (TAT)
CP RT/RW/Developer: Pak RT 081234567890

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format ODP Full
    ODP_FULL_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
ID Valins: VAL-123
Tag Pelanggan: PEL-456
Jarak: 20m
Detail Kendala: ODP Full

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format Pelanggan dan Lainnya
    GENERAL_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Tag Pelanggan: PEL-456
Detail Kendala: {kendala_type}

⚠️ Pastikan semua field diisi dengan benar!"""

    # Media prompts for different kendala types with step-by-step
    TAJ_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 🎥 Video kondisi rumah pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    TAT_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 📸 Foto rencana pemasangan tiang
3. 📸 Bukti sudah menyerahkan file untuk sitac
4. 🎥 Video kondisi rumah pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    ODP_FULL_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 📸 Capture lensa nearest ODP dimana masih dalam range 250m

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    GENERAL_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan

⚠️ Kirim foto sesuai permintaan!"""

    MEDIA_RECEIVED = """✅ Media diterima ({media_count} file)!

📸 Anda masih bisa mengirim foto/video lainnya, atau klik 'Selesai' jika sudah lengkap."""

    DATA_SAVED = "✅ Data berhasil disimpan ke Google Sheet!"
    MEDIA_SAVED = "✅ Media berhasil diupload! ({media_type})"
    MEDIA_ERROR = "❌ Gagal mengupload media. Silakan coba lagi."
    MEDIA_REQUIRED = "⚠️ Anda harus mengirim minimal 1 foto atau video sebelum menyelesaikan input data!"
    HELP_TEXT = "❓ Ketik /start untuk memulai ulang bot.\n\n📋 Bot ini membantu Anda menginput data SC ke Google Sheet dengan mudah."
    RATE_LIMIT = "⏳ Tunggu sebentar sebelum kirim data lagi."


class MenuKeyboards:
    """Static keyboard layouts"""

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
    def back_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.BACK, resize_keyboard=True)

    @staticmethod
    def media_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.MEDIA_OPTIONS, resize_keyboard=True)


# Spreadsheet columns - URUTAN PENTING SESUAI HEADER
SPREADSHEET_COLUMNS = [
    "SC",
    "STO",
    "Detail Kendala",
    "Tag Pelanggan",
    "Nama ODP",
    "ID Valins",
    "Jarak",
    "Jumlah Tiang",
    "Foto dengan Pelanggan/Foto Rumah Pelanggan",
    "Foto Rencana Pemasangan Tiang",
    "Video Kondisi Rumah Pelanggan",
    "Bukti Sudah Menyerahkan File untuk Sitac",
    "Capture Lensa Nearest ODP dimana Masih dalam Range 250m"
]

# Define which fields are required for each kendala type
REQUIRED_FIELDS = {
    KendalaType.TAJ: ["SC", "STO", "Tag Pelanggan", "Detail Kendala"],
    KendalaType.TAT: ["SC", "STO", "Nama ODP", "ID Valins", "Tag Pelanggan", "Jumlah Tiang", "Jarak", "Detail Kendala",
                      "CP RT/RW/Developer"],
    KendalaType.ODP_FULL: ["SC", "STO", "Nama ODP", "ID Valins", "Tag Pelanggan", "Jarak", "Detail Kendala"],
    KendalaType.PELANGGAN: ["SC", "STO", "Tag Pelanggan", "Detail Kendala"],
    KendalaType.LAINNYA: ["SC", "STO", "Tag Pelanggan", "Detail Kendala"]
}

# Define media fields for each kendala type with expected media types
MEDIA_FIELDS_WITH_TYPES = {
    KendalaType.TAJ: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Video Kondisi Rumah Pelanggan", "video", "🎥 Video kondisi rumah pelanggan")
    ],
    KendalaType.TAT: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Foto Rencana Pemasangan Tiang", "photo", "📸 Foto rencana pemasangan tiang"),
        ("Bukti Sudah Menyerahkan File untuk Sitac", "photo", "📸 Bukti sudah menyerahkan file untuk sitac"),
        ("Video Kondisi Rumah Pelanggan", "video", "🎥 Video kondisi rumah pelanggan")
    ],
    KendalaType.ODP_FULL: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Capture Lensa Nearest ODP dimana Masih dalam Range 250m", "photo",
         "📸 Capture lensa nearest ODP dimana masih dalam range 250m")
    ],
    KendalaType.PELANGGAN: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan")
    ],
    KendalaType.LAINNYA: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan")
    ]
}

# Legacy media fields (for backward compatibility)
MEDIA_FIELDS = {
    kendala_type: [item[0] for item in fields]
    for kendala_type, fields in MEDIA_FIELDS_WITH_TYPES.items()
}