import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import Modal from "./Modal";

interface ConfirmOpts {
  title?: string;
  message: ReactNode;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}

interface PromptOpts {
  title?: string;
  label?: string;
  defaultValue?: string;
  placeholder?: string;
  confirmText?: string;
  cancelText?: string;
  multiline?: boolean;
}

type State =
  | ({ kind: "confirm" } & Required<Pick<ConfirmOpts, "message">> & ConfirmOpts)
  | ({ kind: "prompt"; value: string } & PromptOpts);

interface DialogApi {
  confirm: (o: ConfirmOpts) => Promise<boolean>;
  prompt: (o: PromptOpts) => Promise<string | null>;
}

const Ctx = createContext<DialogApi | null>(null);

export function DialogProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State | null>(null);
  const resolver = useRef<((v: unknown) => void) | null>(null);

  const settle = useCallback((value: unknown) => {
    resolver.current?.(value);
    resolver.current = null;
    setState(null);
  }, []);

  const confirm = useCallback(
    (o: ConfirmOpts) =>
      new Promise<boolean>((resolve) => {
        resolver.current = resolve as (v: unknown) => void;
        setState({ kind: "confirm", confirmText: "OK", cancelText: "Cancel", ...o });
      }),
    [],
  );

  const prompt = useCallback(
    (o: PromptOpts) =>
      new Promise<string | null>((resolve) => {
        resolver.current = resolve as (v: unknown) => void;
        setState({
          kind: "prompt",
          value: o.defaultValue ?? "",
          confirmText: "OK",
          cancelText: "Cancel",
          ...o,
        });
      }),
    [],
  );

  // Enter confirms (single-line); Escape cancels.
  useEffect(() => {
    if (!state) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") settle(state.kind === "confirm" ? false : null);
      if (e.key === "Enter") {
        const inTextarea = (e.target as HTMLElement)?.tagName === "TEXTAREA";
        if (state.kind === "confirm") settle(true);
        else if (!inTextarea || e.ctrlKey || e.metaKey) settle(state.value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state, settle]);

  return (
    <Ctx.Provider value={{ confirm, prompt }}>
      {children}
      {state && (
        <Modal
          title={state.title ?? (state.kind === "confirm" ? "Confirm" : "Input")}
          width={460}
          onClose={() => settle(state.kind === "confirm" ? false : null)}
          footer={
            <>
              <button className="btn" onClick={() => settle(state.kind === "confirm" ? false : null)}>
                {state.cancelText}
              </button>
              <button
                className={"btn " + (state.kind === "confirm" && state.danger ? "danger" : "primary")}
                onClick={() => settle(state.kind === "confirm" ? true : state.value)}
                autoFocus={state.kind === "confirm"}
              >
                {state.confirmText}
              </button>
            </>
          }
        >
          {state.kind === "confirm" ? (
            <div style={{ lineHeight: 1.55 }}>{state.message}</div>
          ) : (
            <div className="field">
              {state.label && <label>{state.label}</label>}
              {state.multiline ? (
                <textarea
                  autoFocus
                  value={state.value}
                  placeholder={state.placeholder}
                  onChange={(e) => setState({ ...state, value: e.target.value })}
                  style={{ minHeight: 96 }}
                />
              ) : (
                <input
                  autoFocus
                  value={state.value}
                  placeholder={state.placeholder}
                  onChange={(e) => setState({ ...state, value: e.target.value })}
                />
              )}
              {state.multiline && <span className="help">Press Ctrl/⌘ + Enter to submit.</span>}
            </div>
          )}
        </Modal>
      )}
    </Ctx.Provider>
  );
}

function useDialogs(): DialogApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDialogs must be used within <DialogProvider>");
  return ctx;
}

export const useConfirm = () => useDialogs().confirm;
export const usePrompt = () => useDialogs().prompt;
