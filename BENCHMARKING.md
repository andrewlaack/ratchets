# Benchmarking Blame Options on Django Codebase  
*Shell rule: max 80 characters per line, 3582 blames evaluated*

---

## Saving each blame one at a time to SQLite DB
- **First run:** `11m7.030s`  
- **Cache run:** `0m2.409s`

---

## Saving all blames at the end using `save_blames()`  
*(Still running one insert at a time, no commit/close per insert)*
- **First run:** `11m37.642s`  
- **Cache run:** `0m2.550s`  
- **Conclusion:** No real performance change.

---

## Using `executemany`, with `synchronous=OFF` and `journal_mode=OFF`
*(Performance-optimized SQLite setup)*
- **First run:** `11m55.330s`  
- **Cache run:** `0m2.557s`  
- **Conclusion:** Problem lies with Git speed, not SQLite.

---

## After parallelizing Git blames  
*(System: 4 cores / 8 threads)*
- **First run:** `2m18.302s`  
- **Cache run:** `0m3.878s`

---

## After parallelizing Git blames *and* file map creation  
*(Shell line lookup optimization)*
- **First run:** `2m20.776s`  
- **Cache run:** `0m4.035s`

---

## Thread Count Scaling  
Tested on a 4-core / 8-thread system (one run per setting):

| Thread Count | First Run Time |
|--------------|----------------|
| 8 threads    | 2m20.804s      |
| 16 threads   | 2m17.790s      |
| 32 threads   | 2m15.553s      |
| 64 threads   | 2m7.714s       |
| 128 threads  | 2m8.690s       |

> Improvement levels off beyond 64 threads. System becomes sluggish at higher counts.  
> Using 1x (8 threads) is a reasonable balance between speed and usability.

---

## Conclusion: Git + SQLite Performance Strategy

- Run **map creation** in **series**
- Run **cache lookup** in **series**
- Run **Git blame operations** in **parallel**

---

## Final Optimized Results
- **First run:** `2m16.388s`  
- **Cache run:** `0m2.588s`
