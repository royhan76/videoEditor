# Subscription & Demo System Specification

## Tujuan

Membatasi demo 24 jam dan upgrade paket.

## Paket

-   Demo: Gratis 24 Jam
-   Basic: Rp30.000 / 14 Hari
-   Premium: Rp60.000 / 30 Hari

Pembayaran tahap awal menggunakan **DANA (manual)**.

## Status

-   DEMO
-   ACTIVE
-   EXPIRED
-   SUSPENDED

## Flow

Register -\> DEMO -\> expiredAt=24 jam -\> EXPIRED -\> Overlay Upgrade.

## Firestore

### subscriptions

    ownerId
    status
    plan
    paymentMethod
    paymentStatus
    createdAt
    startAt
    expiredAt
    updatedAt

### invitations

    ownerId
    slug
    templateId
    published

## Middleware

Cek subscription setiap membuka dashboard. Jika EXPIRED tampilkan
overlay yang tidak bisa ditutup.

## Overlay

-   Demo telah berakhir
-   Basic Rp30.000 (14 Hari)
-   Premium Rp60.000 (30 Hari)
-   Tombol Bayar Sekarang

Dashboard tetap bisa dilihat, tetapi edit/upload/publish/template
dikunci.

## Pembayaran DANA

1.  Pilih paket.
2.  Tampilkan nomor/QR DANA.
3.  Upload bukti transfer.
4.  Status WAITING_VERIFICATION.
5.  Admin verifikasi.
6.  Jika diterima -\> ACTIVE dan expiredAt diperpanjang.

## Admin

-   Daftar pembayaran
-   Verifikasi bukti
-   Terima/Tolak

## Phase

1.  Subscription & Demo.
2.  Middleware & Overlay.
3.  UI Paket + Countdown.
4.  Pembayaran Manual DANA.
5.  Aktivasi & Testing.
6.  Future: Midtrans/Xendit, QRIS, WA, Invoice.
