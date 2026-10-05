import { useRef } from 'react';
import { Assistant } from '../../pages/Assistant';

export function AssistantDrawer() {
  const dialog = useRef<HTMLDialogElement>(null);
  return (
    <>
      <button className="assistant-toggle" onClick={() => dialog.current?.showModal()}>
        ✦ Ask assistant
      </button>
      <dialog ref={dialog} className="assistant-drawer" aria-label="Planning assistant">
        <form method="dialog" className="drawer-close">
          <button autoFocus>Close assistant ×</button>
        </form>
        <Assistant />
      </dialog>
    </>
  );
}
