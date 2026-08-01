# Sync Flow Diagram

## High-level flow

```mermaid
flowchart TD
    A[ir.cron every N minutes / Sync Now button] --> B{Auto sync enabled?}
    B -- No --> Z[Skip run]
    B -- Yes --> C[Build TimeOfficeAdapter from settings]
    C --> D[authenticate]
    D -- fails --> E[Log run-level error, abort run]
    D -- ok --> F[Read Last Sync Time]
    F --> G["GET attendance endpoint (since=Last Sync Time)"]
    G -- HTTP/network error --> E
    G -- ok --> H[Normalize each punch]
    H --> I[For each punch]
    I --> J{Employee found by biometric_code?}
    J -- No --> K["Write attendance.sync.log (failed)"]
    J -- Yes --> L{check_in present?}
    L -- Yes --> M{Duplicate check_in exists?}
    M -- Yes, no new checkout --> N["Write attendance.sync.log (skipped)"]
    M -- Yes, new checkout --> O[Update existing hr.attendance.check_out]
    M -- No --> P[Create hr.attendance]
    L -- No, check_out only --> Q{Open attendance exists for employee?}
    Q -- Yes --> R[Close it with check_out]
    Q -- No --> S["Write attendance.sync.log (failed) - orphan checkout"]
    O --> T["Write attendance.sync.log (success)"]
    P --> T
    R --> T
    K --> U[Next punch]
    N --> U
    T --> U
    S --> U
    U --> I
    I -- done --> V[Update Last Sync Time]
    V --> W[Return summary: imported / skipped / failed / duration]
```

## Per-punch decision logic (text form)

```
For each incoming punch:
  1. employee = find hr.employee by biometric_code == employee_code
     -> not found: log FAILED, continue to next punch (never stops the run)

  2. if check_in is present:
       existing = hr.attendance where employee_id = employee
                                  and check_in == punch.check_in
       - existing found, punch has a check_out and existing has none:
             update existing.check_out          -> log SUCCESS
       - existing found, nothing new:
             do nothing                          -> log SKIPPED (duplicate)
       - no existing:
             create hr.attendance(check_in, check_out?)
                                                  -> log SUCCESS

  3. elif check_out only (no check_in in this punch):
       open = latest hr.attendance where employee_id = employee
                                    and check_out is empty
       - open found: set open.check_out           -> log SUCCESS
       - none found: nothing to attach to          -> log FAILED (orphan checkout)

  4. Any unexpected exception while writing the record
     -> caught, logged as FAILED with the error, next punch continues.
```

This is how the module supports overnight shifts (an open
check-in from the previous evening gets its check-out from a punch
received the next morning), multiple punches per day (each check-in
starts its own `hr.attendance`), and missing checkouts (the record is
simply left open until a later sync closes it).
