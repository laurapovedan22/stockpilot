import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useWorkspace } from '../app/Workspace';
import { ErrorState } from '../components/ui/States';
import { post } from '../lib/api';
import type { AssistantAnswer } from '../types/api';

export function Assistant() {
  const { dataset } = useWorkspace();
  const [text, setText] = useState(''),
    [session, setSession] = useState<string | null>(null),
    [messages, setMessages] = useState<{ question: string; answer: AssistantAnswer }[]>([]);
  const request = useMutation({
    mutationFn: (question: string) =>
      post<AssistantAnswer>(`/datasets/${dataset.id}/assistant/messages`, {
        session_id: session,
        text: question,
        context_ids: [],
      }),
    onSuccess: (answer, question) => {
      setSession(answer.session_id);
      setMessages((previous) => [...previous, { question, answer }]);
      setText('');
    },
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">ANSWERS WITH A TRACE</p>
          <h1>Planning assistant</h1>
          <p>Consult saved results and fictional policies. Calculations come from the backend.</p>
        </div>
        <span className="badge mode">Offline explanation mode by default</span>
      </div>
      <section className="panel assistant-panel">
        <p>
          The offline assistant supports product explanations, shortage risk, supplier delays and
          policy retrieval. It cannot approve purchases.
        </p>
        <div className="presets">
          {[
            'Why should I order DEMO-004?',
            'Which products have the highest shortage risk?',
            'What changes if delivery takes four extra days?',
            'What purchasing constraints apply?',
          ].map((question) => (
            <button disabled={request.isPending} key={question} onClick={() => setText(question)}>
              {question}
            </button>
          ))}
        </div>
        <div className="messages" aria-live="polite">
          {messages.map((message, index) => (
            <article key={index}>
              <h3>{message.question}</h3>
              <div className="answer">
                <span className="badge mode">{message.answer.mode}</span>
                <p className="preserve-lines">{message.answer.text}</p>
                <small>
                  Tools consulted: {message.answer.tools.join(', ')} · Dataset as of{' '}
                  {dataset.as_of_date}
                </small>
                {message.answer.sources.length > 0 && (
                  <details>
                    <summary>Sources & result versions</summary>
                    <ul>
                      {message.answer.sources.map((s, i) => (
                        <li key={i}>
                          {s.title ?? s.type} {s.section ? `· ${s.section}` : ''} ·{' '}
                          <code>{s.id}</code> · version {s.version ?? 'Not available'}
                          {s.excerpt && <blockquote>{s.excerpt}</blockquote>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                <Link to="/scenarios" className="text-link">
                  Open scenario controls →
                </Link>
              </div>
            </article>
          ))}
        </div>
        <ErrorState error={request.error} />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            request.mutate(text);
          }}
        >
          <label htmlFor="question">Your question</label>
          <div className="ask-row">
            <textarea
              id="question"
              value={text}
              maxLength={2000}
              rows={3}
              onChange={(e) => setText(e.target.value)}
              required
              placeholder="Ask about a SKU, a saved plan, or purchasing constraints…"
            />
            <button className="primary" disabled={request.isPending || !text.trim()}>
              {request.isPending ? 'Consulting…' : 'Ask →'}
            </button>
          </div>
        </form>
      </section>
    </>
  );
}
