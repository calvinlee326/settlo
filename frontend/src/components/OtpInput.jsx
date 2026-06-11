import { useRef } from 'react';

export default function OtpInput({ value, onChange, length = 6 }) {
  const inputsRef = useRef([]);
  const digits = Array.from({ length }, (_, i) => value[i] || '');

  const setDigit = (index, digit) => {
    const next = digits.slice();
    next[index] = digit;
    onChange(next.join(''));
  };

  const handleChange = (index, event) => {
    const raw = event.target.value.replace(/\D/g, '');
    if (!raw) {
      setDigit(index, '');
      return;
    }
    if (raw.length > 1) {
      // Pasted multiple digits
      const next = digits.slice();
      raw.split('').slice(0, length - index).forEach((d, offset) => {
        next[index + offset] = d;
      });
      onChange(next.join(''));
      const focusIndex = Math.min(index + raw.length, length - 1);
      inputsRef.current[focusIndex]?.focus();
      return;
    }
    setDigit(index, raw);
    if (index < length - 1) {
      inputsRef.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index, event) => {
    if (event.key === 'Backspace' && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  };

  return (
    <div className="flex justify-center gap-2">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(el) => {
            inputsRef.current[index] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete={index === 0 ? 'one-time-code' : 'off'}
          maxLength={length}
          value={digit}
          onChange={(e) => handleChange(index, e)}
          onKeyDown={(e) => handleKeyDown(index, e)}
          className="h-14 w-11 rounded-xl border border-slate-300 bg-white text-center text-xl font-semibold text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
      ))}
    </div>
  );
}
