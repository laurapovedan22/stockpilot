import { useMutation } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { ErrorState } from '../../components/ui/States';
import { post } from '../../lib/api';
import type { Dataset } from '../../types/api';

export function NewDataset({ onCreated }: { onCreated: (dataset: Dataset) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState(''),
    [referenceDate, setReferenceDate] = useState('');
  const create = useMutation({
    mutationFn: () =>
      post<Dataset>('/datasets', {
        name,
        as_of_date: referenceDate,
        source: 'User-supplied CSV',
        currency: 'GBP',
        timezone: 'Europe/London',
      }),
    onSuccess: (dataset) => {
      dialog.current?.close();
      onCreated(dataset);
      setName('');
      setReferenceDate('');
    },
  });
  return (
    <>
      <button
        className="small"
        onClick={() => {
          create.reset();
          dialog.current?.showModal();
        }}
      >
        New dataset +
      </button>
      <dialog ref={dialog} className="dataset-dialog" aria-labelledby="new-dataset-title">
        <h2 id="new-dataset-title">Create a CSV dataset</h2>
        <p>
          Keep your imported observations separate from the synthetic demo. The first sales import
          sets the actual last complete reference day.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <label>
            Dataset name
            <input
              autoFocus
              required
              value={name}
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            Initial reference date
            <input
              type="date"
              value={referenceDate}
              onChange={(event) => setReferenceDate(event.target.value)}
              required
            />
          </label>
          <p className="fineprint">
            GBP · Europe/London. Recorded observations are historical data; stock and costs will be
            imported separately.
          </p>
          <ErrorState error={create.error} />
          <div className="dialog-actions">
            <button type="button" onClick={() => dialog.current?.close()}>
              Cancel
            </button>
            <button className="primary" disabled={create.isPending || !name.trim()}>
              Create dataset
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
