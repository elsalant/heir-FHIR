package dataapi.authz

rule[{"action": {"name":"RedactColumn", "columns": column_names}, "policy": description}] {
  description := "Redact columns tagged as PII in datasets tagged with healthcare = true"
  column_names := [input.resource.metadata.columns[i].name | input.resource.metadata.columns[i].tags.PII]
  count(column_names) > 0
}
rule[{"action": {"name":"Statistics", "columns": column_names}, "policy": description}] {
  description := "Return statistical analysis of glucose in body volume"
  column_names := [input.resource.metadata.columns[i].name | input.resource.metadata.columns[i].tags.stats]
  count(column_names) > 0
}
