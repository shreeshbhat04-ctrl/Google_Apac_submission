# AlloyNative V1 Filter Behavior

This document defines the supported filter semantics for the first release.

## Scope

V1 filters apply only to top-level table columns.

Nested JSONB filtering is out of scope for the first release.

## Supported Operators

These operators are supported:

- `column = value`
- `column__ne = value`
- `column__gt = value`
- `column__gte = value`
- `column__lt = value`
- `column__lte = value`
- `column__in = [value1, value2, ...]`

## Combination Rules

- All filters are combined with `AND`
- Empty `__in` lists are rejected
- Unsupported operators are rejected with a validation error
- Filters target SQL columns, not nested metadata paths

## Examples

```json
{
  "category": "shoes",
  "price__lte": 100,
  "price__gte": 50
}
```

```json
{
  "department": "cardiology",
  "created_at__gte": "2024-01-01"
}
```

```json
{
  "status__in": ["active", "review"]
}
```

## Out Of Scope For V1

- nested JSONB path filtering
- `LIKE` and `ILIKE`
- OR groups
- arbitrary SQL expressions
