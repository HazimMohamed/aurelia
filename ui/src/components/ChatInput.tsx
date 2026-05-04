import TextareaAutosize from "react-textarea-autosize";
import clsx from "clsx";

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onAbort: () => void;
  disabled: boolean;
  sending: boolean;
  canAbort: boolean;
};

export function ChatInput({ value, onChange, onSend, onAbort, disabled, sending, canAbort }: Props) {
  const isBusy = sending;

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter") return;
    if (e.isComposing || e.keyCode === 229) return;
    if (e.shiftKey) return;
    if (disabled) return;
    e.preventDefault();
    onSend();
  }

  return (
    <div className="chat-compose">
      <div className="chat-compose__row">
        <label className="field chat-compose__field">
          <span>Message</span>
          <TextareaAutosize
            value={value}
            disabled={disabled}
            minRows={1}
            maxRows={8}
            placeholder={
              disabled
                ? "Connect to the backend to start chatting…"
                : "Message (↩ to send, Shift+↩ for line breaks)"
            }
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </label>
        <div className="chat-compose__actions">
          {canAbort && (
            <button className={clsx("btn")} onClick={onAbort}>
              Stop
            </button>
          )}
          <button
            className="btn primary"
            disabled={disabled}
            onClick={onSend}
          >
            {isBusy ? "Queue" : "Send"}
            <kbd className="btn-kbd">↵</kbd>
          </button>
        </div>
      </div>
    </div>
  );
}
