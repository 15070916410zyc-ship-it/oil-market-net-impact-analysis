export type Frequency = "daily" | "monthly";
export type PriceRow = { date: string; actual?: number; forecast?: number; lo50?: number; hi50?: number; lo80?: number; hi80?: number; lo95?: number; hi95?: number };
export type DataSeries = { id: string; name: string; nameEn?: string; category?: string; source: string; unit: string; frequency: string; updated: string; color: string };
