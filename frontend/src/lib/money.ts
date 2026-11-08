/** "KES 15,000.00" from the string amount the API sends (Decimals travel as strings so no cent is ever rounded). */
export const money = (amount: string, currency: string) =>
  `${currency} ${Number(amount).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
