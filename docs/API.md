# AcadResult REST API Documentation
## Base URL: `/api/v1/`

All endpoints require authentication (session cookie).
JSON responses are returned for all endpoints.

---

## Endpoints

### Health Check
```
GET /api/v1/health
Auth: None required
Response: { "status": "ok", "service": "AcadResult API" }
```

---

### AI Performance Prediction
```
GET /api/v1/predict/<student_id>
Auth: Student (own only) | HOD | Admin

Response:
{
  "student_id": 1,
  "matric": "CSC/2021/001",
  "name": "Emeka Okafor",
  "risk_level": "At Risk" | "Average" | "Excellent" | "Unknown",
  "predicted_gpa": 3.45,
  "confidence": 0.87,
  "method": "ml_model (Random Forest)" | "rule_based",
  "current_cgpa": 3.20
}

Errors:
  403 - Student accessing another student's prediction
  500 - Model error (falls back to rule_based)
```

---

### GPA Trend Data (for charts)
```
GET /api/v1/student/<student_id>/gpa-trend
Auth: Student (own only) | HOD | Admin

Response:
{
  "labels": ["2023/2024 S1", "2023/2024 S2", "2024/2025 S1"],
  "data": [3.50, 3.75, 4.00]
}
```

---

### Department Statistics
```
GET /api/v1/department/<dept_id>/stats
Auth: HOD | Admin

Response:
{
  "department": "Computer Science",
  "student_count": 120,
  "with_results": 98,
  "average_cgpa": 3.12,
  "classification_distribution": {
    "First Class": 8,
    "Second Class Upper": 32,
    "Second Class Lower": 41,
    "Third Class": 12,
    "Probation/Fail": 5
  }
}
```

---

## Workflow Summary

```
Lecturer → POST score entry → Result(status=draft)
Lecturer → POST submit      → Result(status=pending)
HOD      → POST approve-all → Result(status=approved)
                            → GPA/CGPA computed
                            → Carryovers scheduled
                            → Emails sent (if released)
Student  → GET dashboard    → Sees results + AI prediction
                            → Downloads transcript
HOD      → GET export       → Downloads Excel report
```
