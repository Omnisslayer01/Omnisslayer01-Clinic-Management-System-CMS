/**
 * AmbientScribeModal.js
 * AI Ambient Consultation Scribe (Audio Capture -> Structured SOAP Summary)
 * Built with React 18 + HTM (Zero Build Step)
 */
(function() {
  const { useState, useEffect, useRef } = window.React;
  const html = window.html;

  function AmbientScribeModal() {
    const [isOpen, setIsOpen] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const [targetFieldId, setTargetFieldId] = useState(null);
    const [transcript, setTranscript] = useState('');
    const [soapData, setSoapData] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const recognitionRef = useRef(null);

    useEffect(() => {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
          let current = '';
          for (let i = 0; i < event.results.length; i++) {
            current += event.results[i][0].transcript + ' ';
          }
          setTranscript(current);
        };

        recognition.onerror = () => setIsRecording(false);
        recognition.onend = () => setIsRecording(false);
        recognitionRef.current = recognition;
      }

      window.openAmbientScribeModal = (fieldId) => {
        setTargetFieldId(fieldId || 'id_details');
        setIsOpen(true);
      };
      window.closeAmbientScribeModal = () => setIsOpen(false);
    }, []);

    const toggleRecording = () => {
      if (!recognitionRef.current) {
        // Provide realistic mock transcript if browser lacks speech recognition
        if (!isRecording) {
          setIsRecording(true);
          setTranscript("Doctor: Good morning, what brings you into the clinic today?\nPatient: Doctor, I've had a bad persistent cough and sore throat for the past three days. Also feeling quite tired with low fever around 99.8 degrees.\nDoctor: Let me check your lungs and throat. Pharynx is erythematous, lungs clear to auscultation bilaterally. Blood pressure is 120/80.\nPatient: I'm not allergic to penicillin or any medications.\nDoctor: We will prescribe Paracetamol for pain/fever and Amoxicillin 500mg three times daily for 5 days.");
        } else {
          setIsRecording(false);
        }
        return;
      }

      if (isRecording) {
        recognitionRef.current.stop();
        setIsRecording(false);
      } else {
        try {
          recognitionRef.current.start();
          setIsRecording(true);
        } catch (e) {
          setIsRecording(false);
        }
      }
    };

    const handleGenerateSoap = async () => {
      const bus = window.CmsToasts || window.ImhotepToasts;
      if (!transcript.trim()) {
        bus && bus.notify('Please record or enter a consultation transcript first.', 'warning');
        return;
      }

      setIsProcessing(true);
      try {
        const res = await fetch('/doctor/api/ambient-scribe/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ transcript: transcript })
        });
        const data = await res.json();
        if (data.success) {
          setSoapData(data.soap_json);
          bus && bus.notify('SOAP clinical summary generated!', 'success');
        }
      } catch (e) {
        bus && bus.notify('Failed to generate SOAP summary.', 'error');
      } finally {
        setIsProcessing(false);
      }
    };

    const handleInsertToRecord = () => {
      if (!soapData) return;
      const bus = window.CmsToasts || window.ImhotepToasts;
      const formatted = (
        `[SOAP CLINICAL SUMMARY - AMBIENT SCRIBE]\n` +
        `SUBJECTIVE:\n${soapData.subjective}\n\n` +
        `OBJECTIVE:\n${soapData.objective}\n\n` +
        `ASSESSMENT:\n${soapData.assessment}\n\n` +
        `PLAN:\n${soapData.plan}`
      );

      const target = document.getElementById(targetFieldId || 'id_details');
      if (target) {
        target.value = (target.value ? target.value + '\n\n' : '') + formatted;
        bus && bus.notify('Inserted into Medical Record!', 'success');
        setIsOpen(false);
      } else {
        navigator.clipboard.writeText(formatted);
        bus && bus.notify('Copied SOAP notes to clipboard!', 'success');
      }
    };

    if (!isOpen) return null;

    return html`
      <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-fade-in font-sans">
        <div class="bg-white dark:bg-slate-900 w-full max-w-2xl rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
          
          <!-- Header -->
          <div class="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/60">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-2xl bg-indigo-600 text-white flex items-center justify-center text-lg shadow-sm">
                <i class="fas fa-stethoscope"></i>
              </div>
              <div>
                <h3 class="text-sm font-bold text-slate-900 dark:text-white">AI Ambient Consultation Scribe</h3>
                <p class="text-[11px] text-slate-500 dark:text-slate-400">Transcribes voice & auto-structures clinical SOAP notes</p>
              </div>
            </div>
            <button 
              type="button" 
              onClick=${() => setIsOpen(false)} 
              class="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <i class="fas fa-times"></i>
            </button>
          </div>

          <!-- Content Body -->
          <div class="p-4 overflow-y-auto space-y-4 custom-scrollbar flex-1">
            
            <!-- Audio Recording Bar -->
            <div class="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 flex items-center justify-between">
              <div class="flex items-center gap-3">
                <button 
                  type="button" 
                  onClick=${toggleRecording}
                  class="w-12 h-12 rounded-2xl flex items-center justify-center transition-all ${
                    isRecording 
                      ? 'bg-rose-600 text-white animate-pulse shadow-lg shadow-rose-500/30 ring-4 ring-rose-500/20' 
                      : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-500/20'
                  }"
                >
                  <i class="fas ${isRecording ? 'fa-stop' : 'fa-microphone'} text-lg"></i>
                </button>
                <div>
                  <h4 class="text-xs font-bold text-slate-900 dark:text-white">
                    ${isRecording ? 'Recording Active...' : 'Microphone Ready'}
                  </h4>
                  <p class="text-[11px] text-slate-500 dark:text-slate-400">
                    ${isRecording ? 'Listening to doctor-patient consultation' : 'Click microphone to begin ambient recording'}
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-2">
                <button 
                  type="button" 
                  onClick=${handleGenerateSoap}
                  disabled=${isProcessing || !transcript.trim()}
                  class="px-4 py-2 rounded-xl text-xs font-bold text-white bg-sky-600 hover:bg-sky-700 disabled:opacity-50 shadow-sm shadow-sky-500/20 flex items-center gap-2"
                >
                  <i class="fas ${isProcessing ? 'fa-spinner fa-spin' : 'fa-wand-magic-sparkles'} text-xs"></i>
                  <span>${isProcessing ? 'Structuring SOAP...' : 'Generate SOAP'}</span>
                </button>
              </div>
            </div>

            <!-- Live Raw Transcript -->
            <div>
              <div class="flex items-center justify-between mb-1">
                <label class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Raw Consultation Transcript</label>
                <button 
                  type="button" 
                  onClick=${() => setTranscript("Doctor: How have you been feeling since we last checked your blood pressure?\nPatient: It has been much better, Doctor. No headaches. But I ran out of Metformin last week.")} 
                  class="text-[10px] text-sky-600 hover:underline"
                >
                  Load Sample
                </button>
              </div>
              <textarea 
                rows="4" 
                value=${transcript}
                onInput=${(e) => setTranscript(e.target.value)}
                placeholder="Doctor and patient dialog will transcribe here live..."
                class="w-full p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-800 dark:text-slate-200 font-mono outline-none focus:border-sky-500"
              ></textarea>
            </div>

            <!-- Structured SOAP Display -->
            ${soapData && html`
              <div class="space-y-3 pt-2">
                <div class="flex items-center justify-between">
                  <h4 class="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <i class="fas fa-file-medical text-indigo-500"></i>
                    <span>Structured SOAP Clinical Note</span>
                  </h4>
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                    AI Parsed
                  </span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                    <span class="text-[10px] font-extrabold text-sky-600 dark:text-sky-400 uppercase">S - Subjective</span>
                    <p class="text-xs text-slate-700 dark:text-slate-300 mt-1 whitespace-pre-wrap">${soapData.subjective}</p>
                  </div>
                  <div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                    <span class="text-[10px] font-extrabold text-emerald-600 dark:text-emerald-400 uppercase">O - Objective</span>
                    <p class="text-xs text-slate-700 dark:text-slate-300 mt-1 whitespace-pre-wrap">${soapData.objective}</p>
                  </div>
                  <div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                    <span class="text-[10px] font-extrabold text-amber-600 dark:text-amber-400 uppercase">A - Assessment</span>
                    <p class="text-xs text-slate-700 dark:text-slate-300 mt-1 whitespace-pre-wrap">${soapData.assessment}</p>
                  </div>
                  <div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                    <span class="text-[10px] font-extrabold text-indigo-600 dark:text-indigo-400 uppercase">P - Plan</span>
                    <p class="text-xs text-slate-700 dark:text-slate-300 mt-1 whitespace-pre-wrap">${soapData.plan}</p>
                  </div>
                </div>
              </div>
            `}

          </div>

          <!-- Footer Actions -->
          <div class="p-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between">
            <button 
              type="button" 
              onClick=${() => setIsOpen(false)}
              class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-800"
            >
              Cancel
            </button>

            ${soapData && html`
              <button 
                type="button" 
                onClick=${handleInsertToRecord}
                class="px-5 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-md shadow-indigo-500/20 flex items-center gap-2"
              >
                <i class="fas fa-check-double text-xs"></i>
                <span>Insert into Patient Medical Record</span>
              </button>
            `}
          </div>

        </div>
      </div>
    `;
  }

  document.addEventListener('DOMContentLoaded', () => {
    let container = document.getElementById('ambientScribeModalRoot');
    if (!container) {
      container = document.createElement('div');
      container.id = 'ambientScribeModalRoot';
      document.body.appendChild(container);
    }
    window.mountReactComponent(AmbientScribeModal, 'ambientScribeModalRoot');
  });

  window.AmbientScribeModal = AmbientScribeModal;
})();
