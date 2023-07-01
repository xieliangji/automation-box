```yml
parameters:
  - name: a
    type: string
    regex-pattern: [a-z0-9A-Z]{1,20}
  - name: b
    type: integer
    max-value: 1000
    min-value: 100
  - name: c
    type: boolean
  - name: d
    type: enum<string>
    values: v1,v2,v3
  - name: e
    type: float
    decision: 2
    max-value: 1000.99
    min-value: 0.99
  - name: f
    type: object
    parameters:
      - name: f1
        type: string
        regex-pattern: \\d{1,30}
  - name: g
    type: array<string>
    max-length: 200
    min-length: 0
    regex-pattern: \\w{2,30}
  - name: h
    type: array<integer>
    max-length: 200
    min-length: 1
    max-value: 0
    min-value: -20
```