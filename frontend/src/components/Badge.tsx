interface Props {
  kind: "category" | "priority" | "status" | "provider" | "cache";
  value: string;
}

export function Badge({ kind, value }: Props) {
  return <span className={`badge badge-${kind} badge-${kind}-${value.replace(/[^a-z_]/gi, "-")}`}>{value.replace("_", " ")}</span>;
}
