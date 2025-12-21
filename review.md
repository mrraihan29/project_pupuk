# Code Review

## Urgent
- **BiayaOperasional form vs model mismatch**: `keuangan/forms.py` uses fields `kategori_utama`, `jenis_biaya`, `urgensi`, `status`, `description`, `bukti_foto` while `keuangan/models.py` defines `kategori`, `nominal`, `keterangan`, `foto_bukti`, `is_approved` [keuangan/forms.py#L14-L39](keuangan/forms.py#L14-L39) vs [keuangan/models.py#L52-L87](keuangan/models.py#L52-L87). `ops_create` sets `ops.status` and `ops.kategori_utama`, which do not exist in the model, so the form will fail at render/save and the view will crash [keuangan/views.py#L43-L86](keuangan/views.py#L43-L86), [keuangan/views.py#L90-L121](keuangan/views.py#L90-L121).
- **Invoice balance not updated on payment**: `payment_create` saves `Payment` but never recomputes `Invoice.remaining_balance` or calls `invoice.save()`. `Invoice.save` has the logic, but it is not triggered when only a payment is saved, so invoices never decrease after payments [keuangan/views.py#L18-L42](keuangan/views.py#L18-L42), [keuangan/models.py#L10-L47](keuangan/models.py#L10-L47).
- **Year hardcoded to 2025 for quota checks**: `get_kios_info` uses `year=2025` for both kios and district quota, while other flows use current year, causing wrong quota validation across years [gudang/views.py#L24-L65](gudang/views.py#L24-L65).
- **Unauthenticated access to operational endpoints**: `distribution_create`, `get_kios_info`, `get_so_info`, `get_so_details`, `distribution_list`, `print_document`, `stock_card_list`, `so_list`, `so_create` lack `login_required`, exposing stock/price data and document PDFs to anonymous users [gudang/views.py#L8-L150](gudang/views.py#L8-L150).

## Standard
- **Unit consistency for pricing**: `FertilizerPrice` is treated as per-ton in `laporan_keuangan` and defaults are now in millions, but existing rows may still be per-kg; `get_or_create` can silently reuse per-kg rows leading to 1000× inflation [core/views.py#L187-L211](core/views.py#L187-L211), [core/views.py#L298-L355](core/views.py#L298-L355).
- **Cost grouping vs model choices**: Laporan keuangan groups OPEX with categories `BENSIN`, `SERVIS`, `TOL`, while `BiayaOperasional` choices are `BENSIN`, `MAKAN`, `TOL`, `SERVIS`, `LAIN`. Costs in `MAKAN/LAIN` are dumped into "Biaya Kantor" implicitly; clarify grouping or extend choices [core/views.py#L330-L343](core/views.py#L330-L343), [keuangan/models.py#L52-L87](keuangan/models.py#L52-L87).
- **Document pricing not fixed at issuance**: `print_document` pulls current `FertilizerPrice` instead of storing the price at distribution/invoice time, so historical PDFs can show changed prices [gudang/views.py#L68-L112](gudang/views.py#L68-L112).
- **Concurrency on stock deduction**: `Distribution.save` adjusts `tonnage_current` without `select_for_update`; parallel submissions could oversell stock [gudang/models.py#L66-L117](gudang/models.py#L66-L117).
- **Stock adjustment closing logic**: `StockAdjustment.save` updates `tonnage_current` but never re-evaluates `is_closed`, so a zero stock after opname can remain open [gudang/models.py#L119-L183](gudang/models.py#L119-L183).
- **ENV defaults**: If `SECRET_KEY` or DB env vars are unset, the app crashes at startup; `ALLOWED_HOSTS` from empty env becomes `['']`, which blocks all hosts in production [sim_dp/settings.py#L17-L65](sim_dp/settings.py#L17-L65).

## Opsional
- **Decorator metadata and redirect**: `owner_required` lacks `functools.wraps` and does not preserve `next` for redirect, reducing UX and middleware friendliness [core/decorators.py#L1-L12](core/decorators.py#L1-L12).
- **Hardcoded company info in PDFs**: Company name/address/phone are inline constants, not pulled from settings/config, limiting multi-tenant reuse [gudang/views.py#L89-L107](gudang/views.py#L89-L107).
- **Precision handling**: Multiple API helpers cast `Decimal` to `float`, losing precision and exposing inconsistent JSON when dealing with money/tonnage [gudang/views.py#L35-L65](gudang/views.py#L35-L65), [gudang/views.py#L67-L88](gudang/views.py#L67-L88).
- **Testing gap**: No automated tests across apps (core, gudang, keuangan); high risk of regression for finance flows and stock mutation.
