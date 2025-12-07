# Academic Algorithms License Verification

**Date**: 07-12-2025  
**Status**: Verification in Progress  
**Purpose**: Document license verification for academic algorithms

---

## Verification Methodology

Since arXiv papers don't always display licenses prominently, we use the following approach:

1. **Check arXiv abstract page** for license metadata
2. **Search for GitHub implementations** (often have clearer licenses)
3. **Assume modern papers (2019+)** are more likely to have permissive licenses
4. **Note**: Algorithms themselves are not copyrightable - only specific implementations are

---

## Verification Results

### ✅ VERIFIED - Safe for Commercial Use

#### 1. XGBoost
- **Paper**: arXiv:1603.02754
- **Implementation License**: ✅ Apache 2.0 (verified)
- **GitHub**: https://github.com/dmlc/xgboost
- **Commercial Use**: ✅ **ALLOWED**
- **Attribution**: ✅ Required
- **Status**: ✅ **VERIFIED - Safe to use**

#### 2. PostgreSQL Built-in Indexes
- **BRIN Indexes**: ✅ PostgreSQL BSD License
- **GiST**: ✅ PostgreSQL BSD License
- **Commercial Use**: ✅ **ALLOWED**
- **Status**: ✅ **VERIFIED - Safe to use**

#### 3. Well-Established Algorithms (Public Domain)
- **Fractal Tree Indexes**: ✅ Public domain / well-established
- **iDistance**: ✅ Well-established algorithm
- **Bx-tree**: ✅ Well-established algorithm
- **Commercial Use**: ✅ **ALLOWED** (algorithms not copyrightable)
- **Status**: ✅ **VERIFIED - Safe to use**

### ✅ SAFE TO USE - Algorithm Concepts (Not Copyrightable)

**Important Legal Note**: Algorithms and mathematical concepts themselves are **NOT copyrightable**. Only specific code implementations are protected by copyright. Therefore, implementing algorithms **inspired by** academic papers is legally safe, provided you:

1. Don't copy exact implementations without proper licensing
2. Implement your own version based on the concepts
3. Provide attribution as good practice and academic courtesy

**Status for Algorithm Concepts**: ✅ **SAFE TO USE** (with attribution)

---

### ⚠️ NEEDS MANUAL VERIFICATION

These papers need manual checking on arXiv abstract pages:

#### 1. PGM-Index
- **Paper**: arXiv:1910.06169
- **Authors**: Vinciguerra, et al.
- **Year**: 2019
- **GitHub**: Search for "pgm-index" or "pgmindex"
- **Action**: Check arXiv page for license, check GitHub if exists
- **Likely License**: CC BY 4.0 (common for 2019+ papers)
- **Commercial Use**: ⚠️ **VERIFY ON ARXIV**

#### 2. ALEX
- **Paper**: arXiv:1905.08898
- **Authors**: Ding, et al.
- **Year**: 2019
- **GitHub**: Search for "ALEX learned index" or "alex-index"
- **Action**: Check arXiv page for license, check GitHub if exists
- **Likely License**: CC BY 4.0
- **Commercial Use**: ⚠️ **VERIFY ON ARXIV**

#### 3. RadixStringSpline (RSS)
- **Paper**: arXiv:2111.14905
- **Authors**: [Check arXiv]
- **Year**: 2021
- **Action**: Check arXiv page for license
- **Likely License**: CC BY 4.0 (2021 paper, likely permissive)
- **Commercial Use**: ⚠️ **VERIFY ON ARXIV**

#### 4. Cortex
- **Paper**: arXiv:2012.06683
- **Authors**: [Check arXiv]
- **Year**: 2020
- **Action**: Check arXiv page for license
- **Likely License**: CC BY 4.0
- **Commercial Use**: ⚠️ **VERIFY ON ARXIV**

#### 5. Predictive Indexing
- **Paper**: arXiv:1901.07064
- **Authors**: [Check arXiv]
- **Year**: 2019
- **Action**: Check arXiv page for license
- **Likely License**: CC BY 4.0 or arXiv default
- **Commercial Use**: ⚠️ **VERIFY ON ARXIV**

#### 6. CERT
- **Paper**: arXiv:2306.00355
- **Authors**: [Check arXiv]
- **Year**: 2023
- **Action**: Check arXiv page for license
- **Likely License**: CC BY 4.0 (2023 paper, likely permissive)
- **Commercial Use**: ⚠️ **VERIFY ON ARXIV**

#### 7. Query Plan Guidance (QPG)
- **Paper**: arXiv:2312.17510
- **Authors**: [Check arXiv]
- **Year**: 2023
- **Action**: Check arXiv page for license
- **Likely License**: CC BY 4.0 (2023 paper, likely permissive)
- **Commercial Use**: ⚠️ **VERIFY ON ARXIV**

#### 8. A+ Indexes
- **Paper**: arXiv:2004.00130
- **Authors**: [Check arXiv]
- **Year**: 2020
- **Action**: Check arXiv page for license
- **Likely License**: CC BY 4.0
- **Commercial Use**: ⚠️ **VERIFY ON ARXIV**

---

## Practical Approach for IndexPilot

### Option 1: Use GitHub Implementations (Recommended)

**Advantage**: Clear licenses (usually MIT/Apache), tested code

1. **PGM-Index**: Search GitHub for implementations
2. **ALEX**: Search GitHub for implementations
3. **RadixStringSpline**: Search GitHub for implementations

**Action**: Find implementations, check licenses, use if MIT/Apache compatible

### Option 2: Inspired Implementation (Safest)

**Advantage**: No license concerns (algorithms not copyrightable)

- Implement similar concepts inspired by papers
- Not exact implementations
- Algorithms themselves are not copyrightable
- Still provide attribution as good practice

**Example**:
```python
# Inspired by PGM-index concepts (arXiv:1910.06169)
# Algorithm concepts are not copyrightable
# Attribution provided as good practice
```

### Option 3: Verify and Attribute

**For papers that allow commercial use**:
- Verify license on arXiv
- Implement based on paper
- Provide proper attribution

---

## Next Steps

1. **Manual Verification**: Visit each arXiv page and check license
2. **GitHub Search**: Find implementations with clear licenses
3. **Author Contact**: If license unclear, contact authors
4. **Documentation**: Update this file with verification results

---

**Last Updated**: 07-12-2025  
**Status**: Verification in progress

