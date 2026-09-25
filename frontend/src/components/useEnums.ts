import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Enums } from "../api/types";

/** Domain vocabulary comes from the server, never from a list in the UI code. */
export function useEnums(): Enums | null {
  const [enums, setEnums] = useState<Enums | null>(null);
  useEffect(() => {
    let alive = true;
    api
      .getEnums()
      .then((e) => alive && setEnums(e))
      .catch(() => alive && setEnums({ categories: [], priorities: [], statuses: [] }));
    return () => {
      alive = false;
    };
  }, []);
  return enums;
}
