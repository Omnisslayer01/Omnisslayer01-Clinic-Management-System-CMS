/**
 * AiBookingModal.js
 * Conversational Voice & Chat Booking Agent with Emergency Keyword Triage
 * Built with React 18 + HTM (Zero Build Step)
 */
(function() {
  const { useState, useEffect, useRef } = window.React;
  const html = window.html;

  function AiBookingModal() {
    const [isOpen, setIsOpen] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const [messages, setMessages] = useState([
      {
        sender: 'bot',
        text: 'Hello! I am your MedCare AI Booking Assistant. I can help you schedule a consultation with Dr. Zamil or check slot availability. How are you feeling today?'
      }
    ]);
    const [inputText, setInputText] = useState('');
    const [patientName, setPatientName] = useState('');
    const [patientPhone, setPatientPhone] = useState('');
    const [isEmergency, setIsEmergency] = useState(false);
    const [emergencyDetails, setEmergencyDetails] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    
    const recognitionRef = useRef(null);
    const messagesEndRef = useRef(null);

    // Initialize Web Speech API if supported
    useEffect(() => {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          setInputText(transcript);
          setIsListening(false);
          handleSendMessage(transcript);
        };

        recognition.onerror = () => {
          setIsListening(false);
        };

        recognition.onend = () => {
          setIsListening(false);
        };

        recognitionRef.current = recognition;
      }

      // Expose opener globally
      window.openAiBookingModal = () => setIsOpen(true);
      window.closeAiBookingModal = () => setIsOpen(false);
    }, [patientName, patientPhone]);

    useEffect(() => {
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [messages, isEmergency]);

    const toggleVoice = () => {
      if (!recognitionRef.current) {
        const bus = window.CmsToasts || window.ImhotepToasts;
        bus && bus.notify('Speech recognition is not supported in this browser. Please type your message.', 'warning');
        return;
      }
      if (isListening) {
        recognitionRef.current.stop();
        setIsListening(false);
      } else {
        try {
          recognitionRef.current.start();
          setIsListening(true);
        } catch (e) {
          setIsListening(false);
        }
      }
    };

    const handleSendMessage = async (textToSend) => {
      const text = textToSend || inputText;
      if (!text.trim() || isSubmitting) return;

      const userMsg = { sender: 'user', text };
      setMessages(prev => [...prev, userMsg]);
      setInputText('');
      setIsSubmitting(true);

      try {
        const res = await fetch('/doctor/api/ai-booking-agent/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            name: patientName,
            phone: patientPhone
          })
        });
        const data = await res.json();

        if (data.is_emergency) {
          setIsEmergency(true);
          setEmergencyDetails(data);
          setMessages(prev => [...prev, {
            sender: 'bot',
            text: data.bot_reply,
            isEmergency: true
          }]);
        } else {
          setMessages(prev => [...prev, {
            sender: 'bot',
            text: data.bot_reply,
            status: data.status
          }]);
          const bus = window.CmsToasts || window.ImhotepToasts;
          if (data.status === 'booked' && bus) {
            bus.notify('Appointment confirmed! Check-in SMS dispatched.', 'success');
          }
        }
      } catch (err) {
        setMessages(prev => [...prev, {
          sender: 'bot',
          text: "I'm having trouble connecting to the booking engine. Please try again or call the front desk directly."
        }]);
      } finally {
        setIsSubmitting(false);
      }
    };

    if (!isOpen) return null;

    return html`
      <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-fade-in font-sans">
        <div class="bg-white dark:bg-slate-900 w-full max-w-lg rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col max-h-[85vh] overflow-hidden">
          
          <!-- Header -->
          <div class="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between ${isEmergency ? 'bg-rose-600 text-white' : 'bg-slate-50 dark:bg-slate-800/50'}">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-2xl ${isEmergency ? 'bg-white/20 text-white' : 'bg-sky-600 text-white'} flex items-center justify-center text-lg shadow-sm">
                <i class="fas ${isEmergency ? 'fa-triangle-exclamation' : 'fa-robot'}"></i>
              </div>
              <div>
                <h3 class="text-sm font-bold ${isEmergency ? 'text-white' : 'text-slate-900 dark:text-white'}">
                  ${isEmergency ? 'EMERGENCY TRIAGE ESCALATION' : 'MedCare Conversational Booking Agent'}
                </h3>
                <p class="text-[11px] ${isEmergency ? 'text-white/80' : 'text-slate-500 dark:text-slate-400'}">
                  ${isEmergency ? 'Standard booking suspended' : 'Voice-enabled AI slot reservation & clinical triage'}
                </p>
              </div>
            </div>
            <button 
              type="button" 
              onClick=${() => setIsOpen(false)} 
              class="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 ${isEmergency ? 'text-white/80 hover:text-white' : ''}"
            >
              <i class="fas fa-times"></i>
            </button>
          </div>

          <!-- Emergency Banner -->
          ${isEmergency && html`
            <div class="p-3 bg-rose-50 dark:bg-rose-950/80 border-b border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-200 flex items-center gap-3">
              <i class="fas fa-bell text-rose-600 animate-bounce text-base"></i>
              <div class="flex-1">
                <strong>Critical symptom detected:</strong> "${emergencyDetails?.trigger}". Escalated to duty nurse and on-call ER staff.
              </div>
              <a href="tel:911" class="px-3 py-1 bg-rose-600 text-white font-bold rounded-lg hover:bg-rose-700 text-[11px] shrink-0">
                Call 911
              </a>
            </div>
          `}

          <!-- Caller Identity Form -->
          <div class="p-3 border-b border-slate-100 dark:border-slate-800 grid grid-cols-2 gap-2 bg-slate-50/50 dark:bg-slate-900/30">
            <div>
              <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Patient Name</label>
              <input 
                type="text" 
                placeholder="e.g. Sarah Jenkins" 
                value=${patientName} 
                onInput=${(e) => setPatientName(e.target.value)}
                class="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-800 dark:text-white outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Phone Number</label>
              <input 
                type="text" 
                placeholder="e.g. +1 555-0144" 
                value=${patientPhone} 
                onInput=${(e) => setPatientPhone(e.target.value)}
                class="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-800 dark:text-white outline-none focus:border-sky-500"
              />
            </div>
          </div>

          <!-- Chat Conversation Log -->
          <div class="flex-1 overflow-y-auto p-4 space-y-3 min-h-[260px] max-h-[350px] custom-scrollbar">
            ${messages.map((m, idx) => html`
              <div key=${idx} class="flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}">
                <div class="max-w-[82%] p-3 rounded-2xl text-xs leading-relaxed ${
                  m.sender === 'user' 
                    ? 'bg-sky-600 text-white rounded-br-none shadow-sm' 
                    : m.isEmergency 
                      ? 'bg-rose-100 dark:bg-rose-950/80 text-rose-900 dark:text-rose-100 border border-rose-300 dark:border-rose-800 rounded-bl-none font-medium'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-bl-none'
                }">
                  ${m.sender === 'bot' && html`
                    <div class="flex items-center gap-1.5 mb-1 font-bold ${m.isEmergency ? 'text-rose-700 dark:text-rose-300' : 'text-sky-600 dark:text-sky-400'}">
                      <i class="fas ${m.isEmergency ? 'fa-triangle-exclamation' : 'fa-robot'} text-[10px]"></i>
                      <span>${m.isEmergency ? 'Clinical Triage Alert' : 'MedCare Bot'}</span>
                    </div>
                  `}
                  <p class="whitespace-pre-wrap">${m.text}</p>
                </div>
              </div>
            `)}
            <div ref=${messagesEndRef}></div>
          </div>

          <!-- Quick Symptom Prompts -->
          <div class="px-3 py-1.5 border-t border-slate-100 dark:border-slate-800 flex items-center gap-1.5 overflow-x-auto text-[11px] bg-slate-50/40 dark:bg-slate-800/30">
            <span class="text-slate-400 shrink-0 text-[10px]">Quick:</span>
            <button 
              type="button" 
              onClick=${() => handleSendMessage("I need a routine checkup tomorrow morning")} 
              class="px-2 py-0.5 rounded-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 whitespace-nowrap hover:border-sky-400"
            >
              Routine Checkup
            </button>
            <button 
              type="button" 
              onClick=${() => handleSendMessage("I have had a bad cough and sore throat for 3 days")} 
              class="px-2 py-0.5 rounded-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 whitespace-nowrap hover:border-sky-400"
            >
              Cough & Sore Throat
            </button>
            <button 
              type="button" 
              onClick=${() => handleSendMessage("Patient experiencing severe chest pain and trouble breathing")} 
              class="px-2 py-0.5 rounded-md bg-rose-50 dark:bg-rose-950 border border-rose-200 dark:border-rose-900 text-rose-600 dark:text-rose-400 whitespace-nowrap hover:bg-rose-100"
            >
              🚨 Test Emergency Triage
            </button>
          </div>

          <!-- Input Controls (Voice & Text) -->
          <div class="p-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center gap-2">
            <button 
              type="button" 
              onClick=${toggleVoice}
              title=${isListening ? "Listening... click to stop" : "Speak using microphone"}
              class="w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                isListening 
                  ? 'bg-rose-600 text-white animate-pulse shadow-md shadow-rose-500/30' 
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-sky-50 dark:hover:bg-sky-950 hover:text-sky-600'
              }"
            >
              <i class="fas ${isListening ? 'fa-microphone-slash' : 'fa-microphone'} text-sm"></i>
            </button>

            <input 
              type="text" 
              placeholder=${isListening ? "Listening to your voice..." : "Describe symptoms or booking request..."}
              value=${inputText}
              onInput=${(e) => setInputText(e.target.value)}
              onKeyDown=${(e) => e.key === 'Enter' && handleSendMessage()}
              class="flex-1 px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
            />

            <button 
              type="button" 
              onClick=${() => handleSendMessage()}
              disabled=${isSubmitting || !inputText.trim()}
              class="px-3.5 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm shadow-sky-500/20"
            >
              <span>Send</span>
              <i class="fas fa-paper-plane text-[10px]"></i>
            </button>
          </div>

        </div>
      </div>
    `;
  }

  // Mount component into document body
  document.addEventListener('DOMContentLoaded', () => {
    let container = document.getElementById('aiBookingModalRoot');
    if (!container) {
      container = document.createElement('div');
      container.id = 'aiBookingModalRoot';
      document.body.appendChild(container);
    }
    window.mountReactComponent(AiBookingModal, 'aiBookingModalRoot');
  });

  window.AiBookingModal = AiBookingModal;
})();
