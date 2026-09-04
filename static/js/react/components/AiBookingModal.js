/**
 * AiBookingModal.js — Calm, voice-enabled patient booking assistant
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
        text: "Hello, I'm your clinic booking assistant. I can check when the doctor is available and help you book an appointment. How can I help you today?"
      }
    ]);
    const [inputText, setInputText] = useState('');
    const [patientName, setPatientName] = useState('');
    const [patientPhone, setPatientPhone] = useState('');
    const [isEmergency, setIsEmergency] = useState(false);
    const [emergencyDetails, setEmergencyDetails] = useState(null);
    const [lastPriority, setLastPriority] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const recognitionRef = useRef(null);
    const messagesEndRef = useRef(null);

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
        recognition.onerror = () => setIsListening(false);
        recognition.onend = () => setIsListening(false);
        recognitionRef.current = recognition;
      }
      window.openAiBookingModal = () => setIsOpen(true);
      window.closeAiBookingModal = () => setIsOpen(false);
    }, [patientName, patientPhone]);

    useEffect(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isEmergency]);

    const toggleVoice = () => {
      if (!recognitionRef.current) {
        window.CmsToasts?.notify('Voice input is not supported in this browser. Please type your message.', 'warning');
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

      setMessages(prev => [...prev, { sender: 'user', text }]);
      setInputText('');
      setIsSubmitting(true);

      const isConfirm = /^(yes|yes, book|book it|confirm|book appointment)/i.test(text.trim());

      try {
        const res = await fetch('/doctor/api/ai-booking-agent/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            name: patientName,
            phone: patientPhone,
            confirm_booking: isConfirm,
          })
        });
        const data = await res.json();

        if (data.is_emergency) {
          setIsEmergency(true);
          setEmergencyDetails(data);
          setMessages(prev => [...prev, { sender: 'bot', text: data.bot_reply, isEmergency: true }]);
        } else {
          if (data.priority) setLastPriority({ tier: data.priority, score: data.risk_score });
          setMessages(prev => [...prev, { sender: 'bot', text: data.bot_reply, status: data.status, priority: data.priority }]);
          if (data.status === 'booked') {
            window.CmsToasts?.notify('Appointment confirmed!', 'success');
          }
        }
      } catch (err) {
        setMessages(prev => [...prev, {
          sender: 'bot',
          text: "I'm having trouble connecting right now. Please try again or call the clinic directly."
        }]);
      } finally {
        setIsSubmitting(false);
      }
    };

    if (!isOpen) return null;

    return html`
      <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/20 backdrop-blur-sm animate-fade-in font-sans">
        <div class="bg-white w-full max-w-lg rounded-2xl border border-sky-100 shadow-xl flex flex-col max-h-[85vh] overflow-hidden">

          <!-- Header -->
          <div class="p-4 border-b border-sky-50 flex items-center justify-between ${isEmergency ? 'bg-rose-50' : 'bg-sky-50/50'}">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl ${isEmergency ? 'bg-rose-100 text-rose-600' : 'bg-sky-100 text-sky-600'} flex items-center justify-center">
                <i class="fas ${isEmergency ? 'fa-triangle-exclamation' : 'fa-headset'}"></i>
              </div>
              <div>
                <h3 class="text-sm font-semibold text-slate-800">${isEmergency ? 'Emergency Alert' : 'Booking Assistant'}</h3>
                <p class="text-[11px] text-slate-400">${isEmergency ? 'Immediate attention required' : 'Voice & chat · availability & booking'}</p>
              </div>
            </div>
            <button type="button" onClick=${() => setIsOpen(false)} class="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-white">
              <i class="fas fa-times"></i>
            </button>
          </div>

          ${isEmergency && html`
            <div class="p-3 bg-rose-50 border-b border-rose-100 text-xs text-rose-700 flex items-center gap-3">
              <i class="fas fa-bell text-rose-500"></i>
              <span class="flex-1">Critical symptom: "${emergencyDetails?.trigger}". Please seek emergency care if needed.</span>
              <a href="tel:911" class="px-3 py-1 bg-rose-500 text-white rounded-lg text-[11px] font-medium shrink-0">Call 911</a>
            </div>
          `}

          ${lastPriority && !isEmergency && html`
            <div class="px-4 py-2 bg-sky-50/80 border-b border-sky-50 text-[11px] text-sky-700 flex items-center gap-2">
              <i class="fas fa-heart-pulse text-sky-400"></i>
              <span>Priority: <strong>${lastPriority.tier}</strong>${lastPriority.score ? ` (risk ${lastPriority.score}/100)` : ''}</span>
            </div>
          `}

          <!-- Patient info -->
          <div class="p-3 border-b border-sky-50 grid grid-cols-2 gap-2 bg-white">
            <div>
              <label class="block text-[10px] font-medium text-slate-400 mb-1">Your name</label>
              <input type="text" placeholder="Full name" value=${patientName}
                onInput=${(e) => setPatientName(e.target.value)}
                class="w-full px-2.5 py-1.5 rounded-lg border border-sky-100 text-xs text-slate-800 outline-none focus:border-sky-300" />
            </div>
            <div>
              <label class="block text-[10px] font-medium text-slate-400 mb-1">Phone</label>
              <input type="text" placeholder="Phone number" value=${patientPhone}
                onInput=${(e) => setPatientPhone(e.target.value)}
                class="w-full px-2.5 py-1.5 rounded-lg border border-sky-100 text-xs text-slate-800 outline-none focus:border-sky-300" />
            </div>
          </div>

          <!-- Chat -->
          <div class="flex-1 overflow-y-auto p-4 space-y-3 min-h-[240px] max-h-[320px] custom-scrollbar bg-[#f8fbff]">
            ${messages.map((m, idx) => html`
              <div key=${idx} class="flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}">
                <div class="max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed ${
                  m.sender === 'user'
                    ? 'bg-sky-500 text-white rounded-br-md'
                    : m.isEmergency
                      ? 'bg-rose-50 text-rose-800 border border-rose-100 rounded-bl-md'
                      : 'bg-white text-slate-700 border border-sky-50 rounded-bl-md shadow-sm'
                }">
                  <p class="whitespace-pre-wrap">${m.text}</p>
                </div>
              </div>
            `)}
            <div ref=${messagesEndRef}></div>
          </div>

          <!-- Quick prompts -->
          <div class="px-3 py-2 border-t border-sky-50 flex gap-1.5 overflow-x-auto text-[11px] bg-white">
            <button type="button" onClick=${() => handleSendMessage("When is the doctor free tomorrow?")}
              class="px-2.5 py-1 rounded-lg bg-sky-50 text-sky-600 border border-sky-100 whitespace-nowrap hover:bg-sky-100">Check availability</button>
            <button type="button" onClick=${() => handleSendMessage("I'd like to book a routine checkup")}
              class="px-2.5 py-1 rounded-lg bg-sky-50 text-sky-600 border border-sky-100 whitespace-nowrap hover:bg-sky-100">Book checkup</button>
            <button type="button" onClick=${() => handleSendMessage("I have had fever and body aches for 2 days")}
              class="px-2.5 py-1 rounded-lg bg-sky-50 text-sky-600 border border-sky-100 whitespace-nowrap hover:bg-sky-100">Report symptoms</button>
          </div>

          <!-- Input -->
          <div class="p-3 border-t border-sky-50 bg-white flex items-center gap-2">
            <button type="button" onClick=${toggleVoice} title="Voice input"
              class="w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                isListening ? 'bg-rose-100 text-rose-500 animate-pulse' : 'bg-sky-50 text-sky-500 hover:bg-sky-100'
              }">
              <i class="fas ${isListening ? 'fa-stop' : 'fa-microphone'} text-sm"></i>
            </button>
            <input type="text" placeholder=${isListening ? 'Listening...' : 'Type or speak your message...'}
              value=${inputText} onInput=${(e) => setInputText(e.target.value)}
              onKeyDown=${(e) => e.key === 'Enter' && handleSendMessage()}
              class="flex-1 px-3 py-2 rounded-xl border border-sky-100 text-xs text-slate-800 outline-none focus:border-sky-300 bg-[#f8fbff]" />
            <button type="button" onClick=${() => handleSendMessage()} disabled=${isSubmitting || !inputText.trim()}
              class="px-3.5 py-2 rounded-xl bg-sky-500 hover:bg-sky-600 disabled:opacity-40 text-white text-xs font-medium transition-colors">
              Send
            </button>
          </div>
        </div>
      </div>
    `;
  }

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
