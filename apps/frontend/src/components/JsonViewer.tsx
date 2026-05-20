export function JsonViewer({ value }: { value: unknown }) {
  return (
    <pre className="max-h-[540px] overflow-auto rounded-card bg-[#332c28] p-4 text-xs leading-relaxed text-[#f7efe8]">
      {JSON.stringify(value ?? {}, null, 2)}
    </pre>
  );
}

