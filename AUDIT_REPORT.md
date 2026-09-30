# 📋 AUDIT REPORT - Sistem Prediksi Parlay Termux

**Tanggal Audit:** 2026-09-30  
**Versi Script:** 2797e469 (Main Push)  
**Status Keseluruhan:** ⚠️ **PARTIAL - Butuh Perbaikan Keamanan**

---

## 🎯 RINGKASAN

| Metrik | Score | Status |
|--------|-------|--------|
| **Error Handling** | 7/10 | ⚠️ Ada bare except |
| **Security** | 6/10 | ⚠️ API key logging, path validation |
| **Code Quality** | 8/10 | ✅ Clean, well-structured |
| **Documentation** | 9/10 | ✅ Excellent docstrings |
| **Testing** | 4/10 | 🔴 No unit tests |
| **Deployment Ready** | 6/10 | ⚠️ Butuh hardening security |

**Overall Score: 6.7/10** → DAPAT DIGUNAKAN DENGAN PATCH KEAMANAN

---

## 📌 ISSUE DITEMUKAN (13 Total)

### 🔴 **HIGH SEVERITY (5)**

#### 1. Bare `except: pass` Silent Failure
**File:** `scripts/fetch_api.py:71`  
**Severity:** 🔴 HIGH  
**Impact:** Sulit debug jika ada error tak terduga  

```python
# MASALAH
except json.JSONDecodeError:
    try:
        os.remove(cache_path)
    except OSError:
        pass  # ❌ Silent failure - tidak tahu apa yang error
```

**Fix:**
```python
except json.JSONDecodeError:
    try:
        os.remove(cache_path)
    except OSError as exc:
        logging.warning(f"Cache delete failed: {exc}")
```

---

#### 2. Unsafe API Response Parsing
**File:** `scripts/fetch_api.py:107-110`  
**Severity:** 🔴 HIGH  
**Impact:** Bisa crash jika API berubah format  

```python
# MASALAH
data = fetch_api("/fixtures", {})
if data and "fixtures" in data:  # ❌ Tidak cek apakah data dict
    return data["fixtures"]
```

**Fix:**
```python
data = fetch_api("/fixtures", {})
if isinstance(data, dict) and "fixtures" in data:
    fixtures = data.get("fixtures", [])
    if isinstance(fixtures, list):
        return fixtures
return []
```

---

#### 3. API Key Exposed in Logs
**File:** `scripts/fetch_api.py:186`  
**Severity:** 🔴 HIGH  
**Impact:** API key bisa ketahuan di log files  

```python
# MASALAH
logging.info(f"Fetch completed. Total rows: {len(df_final)}")
# ❌ Jika error, full stack trace bisa terlihat dengan API_KEY
```

**Fix:**
```python
# Selalu mask sensitive data
api_key_masked = API_KEY[:-4] if API_KEY else "NOT_SET"
print(f"[INFO] API Key: ***{api_key_masked[-4:]}")
```

---

#### 4. No Input Validation for Path Traversal
**File:** `scripts/fetch_api.py:32`  
**Severity:** 🔴 HIGH  
**Impact:** CAGE_PATH bisa di-exploit traversal  

```python
# MASALAH
CAGE_PATH = os.getenv("CAGE_PATH", "")  # ❌ Tidak validasi path

# Attacker bisa set CAGE_PATH="../../../etc/passwd"
```

**Fix:**
```python
_cage_raw = os.getenv("CAGE_PATH", "")
CAGE_PATH = str(Path(_cage_raw).resolve())
if not CAGE_PATH.startswith(str(ROOT)):
    raise ValueError("CAGE_PATH harus dalam ROOT directory")
```

---

#### 5. Unsafe subprocess.run without Timeout
**File:** `menus/main_menu.py:117-119`  
**Severity:** 🔴 HIGH  
**Impact:** Script bisa hang infinite jika child process error  

```python
# MASALAH
subprocess.run(
    [sys.executable, str(script_path)],
    cwd=str(ROOT),
    check=False,
)  # ❌ Tidak ada timeout
```

**Fix:**
```python
subprocess.run(
    [sys.executable, str(script_path)],
    cwd=str(ROOT),
    check=False,
    timeout=3600,  # 1 jam max
)
```

---

### 🟠 **MEDIUM SEVERITY (5)**

#### 6. File Permissions Not Secure
**File:** `scripts/fetch_api.py:86-89`  
**Severity:** 🟠 MEDIUM  
**Impact:** Cache files world-readable (API keys bisa exposed)  

```python
# MASALAH
with open(cache_path, 'w', encoding='utf-8') as file:
    json.dump(cache_data, file)
    # ❌ Default umask 644, siapa saja bisa baca
```

**Fix:**
```python
with open(cache_path, 'w', encoding='utf-8') as file:
    json.dump(cache_data, file)
os.chmod(cache_path, 0o640)  # Hanya owner+group baca
```

---

#### 7. Import Statement Not Defensive
**File:** `menus/fetch_api.py:76-77`  
**Severity:** 🟠 MEDIUM  
**Impact:** Menu crash jika fetch_api module error  

```python
# MASALAH
from scripts.fetch_api import fetch_api
# ❌ Tidak handle jika module tidak bisa di-import
```

**Fix:**
```python
try:
    from scripts.fetch_api import fetch_api
except ImportError as exc:
    print(Fore.RED + f"[ERROR] Cannot import fetch_api: {exc}")
    return
```

---

#### 8. DataFrame Column Validation Missing
**File:** `menus/fetch_api.py:105-115`  
**Severity:** 🟠 MEDIUM  
**Impact:** Deduplikasi fail jika kolom berubah  

```python
# MASALAH
key_cols = [col for col in ['match_id', 'team', 'is_home'] if col in ...]
# ❌ Tidak validasi apakah kolom ada di df_old
```

**Fix:**
```python
required_cols = ['match_id', 'team', 'is_home']
missing = set(required_cols) - set(df_old.columns)
if missing:
    raise ValueError(f"Missing columns in df_old: {missing}")
```

---

#### 9. No CWD Path Validation
**File:** `menus/main_menu.py:119`  
**Severity:** 🟠 MEDIUM  
**Impact:** Bisa execute script dari wrong directory  

```python
# MASALAH
subprocess.run([...], cwd=str(ROOT), ...)
# ❌ ROOT bisa relative path, bisa resolve error
```

**Fix:**
```python
subprocess.run([...], cwd=str(ROOT.resolve()), ...)
```

---

#### 10. Timestamp Collision Risk
**File:** `menus/fetch_api.py:55`  
**Severity:** 🟠 MEDIUM  
**Impact:** Backup files bisa overwrite jika run 2x dalam 1 detik  

```python
# MASALAH
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')  # ❌ 2 run dalam 1s = collision
```

**Fix:**
```python
stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Add milliseconds
```

---

### 🟡 **LOW SEVERITY (3)**

#### 11. No Test Coverage
**File:** Repository root  
**Severity:** 🟡 LOW  
**Impact:** Sulit maintain & refactor  

**Fix:** Buat `tests/` folder dengan pytest

---

#### 12. Missing Type Hints
**File:** All scripts  
**Severity:** 🟡 LOW  
**Impact:** Sulit maintain, IDE autocompletion kurang  

**Fix:** Tambah `from typing import Dict, List, Optional`

---

#### 13. No Rate Limit Monitoring
**File:** `scripts/fetch_api.py`  
**Severity:** 🟡 LOW  
**Impact:** Bisa kena rate limit di tengah fetch  

**Fix:** Tambah retry logic dengan exponential backoff

---

## ✅ PERBAIKAN YANG SUDAH DILAKUKAN

✅ Cache JSON error handling  
✅ Column mapping ekstensif  
✅ Deduplikasi sebelum merge  
✅ EOFError handling di menu  
✅ Rate limiting 2s/request  
✅ Folder structure auto-create  
✅ Backup sebelum overwrite  

---

## 📋 ACTION ITEMS (Priority Queue)

### Week 1: URGENT
- [ ] Fix bare `except: pass` → use `except Exception as exc`
- [ ] Add `isinstance()` validation untuk API response
- [ ] Mask API_KEY di semua logs → gunakan `***` suffix
- [ ] Validate CAGE_PATH untuk path traversal
- [ ] Add timeout=3600 ke subprocess.run()

### Week 2: HIGH
- [ ] Set file permissions 0o640 untuk cache & CSV
- [ ] Add try/except import di menus/fetch_api.py
- [ ] Validate DataFrame columns sebelum deduplicate
- [ ] Use ROOT.resolve() untuk CWD
- [ ] Add milliseconds ke timestamp backup

### Week 3+: MEDIUM
- [ ] Create tests/ folder dengan pytest coverage
- [ ] Add type hints ke semua functions
- [ ] Implement retry with exponential backoff untuk API
- [ ] Add rate limit monitoring dengan logging
- [ ] Create security.md dengan best practices

---

## 🔒 SECURITY CHECKLIST

```
[x] Error handling robust
[ ] Input validation strict
[ ] Output sanitized
[ ] Logging no secrets
[ ] File permissions 640
[ ] Subprocess timeout
[ ] Path traversal protected
[ ] Dependencies scanned
[ ] Test coverage >80%
[ ] Documentation complete
```

---

## 📞 NEXT STEPS

1. **Apply urgent fixes** → scripts/fetch_api_v2.py
2. **Add unit tests** → tests/test_fetch_api.py
3. **Security hardening** → SECURITY.md guidelines
4. **Code review** → 2nd pair of eyes
5. **Deploy to staging** → Test 1 minggu
6. **Production deployment** → Dengan monitoring

---

**Audit Status:** ⚠️ CONDITIONAL PASS  
**Recommendation:** Deploy to production dengan semua HIGH severity fixes applied.

