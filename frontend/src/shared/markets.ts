/**
 * Crypto-only market universe kept aligned with coinbot_common.data.universe.
 */

export type ProductId = "coinbot";
export type DataSource = "auto" | "okx";
export type AssetType = "crypto";

export interface SupportedInstrument {
  symbol: string;
  name: string;
  exchange: string;
  asset_type: AssetType;
  currency: string;
  default_source: DataSource;
  products: ProductId[];
  aliases: string[];
  description: string;
}

export const MARKET_UNIVERSE: readonly SupportedInstrument[] = [
  {
    symbol: "BTC-USDT",
    name: "Bitcoin / USDT Spot",
    exchange: "OKX",
    asset_type: "crypto",
    currency: "USDT",
    default_source: "okx",
    products: ["coinbot"],
    aliases: ["BTCUSDT", "BTC/USDT", "BTC-USD"],
    description: "Crypto spot market pair.",
  },
  {
    symbol: "ETH-USDT",
    name: "Ethereum / USDT Spot",
    exchange: "OKX",
    asset_type: "crypto",
    currency: "USDT",
    default_source: "okx",
    products: ["coinbot"],
    aliases: ["ETHUSDT", "ETH/USDT", "ETH-USD"],
    description: "Crypto spot market pair.",
  },
  {
    symbol: "SOL-USDT",
    name: "Solana / USDT Spot",
    exchange: "OKX",
    asset_type: "crypto",
    currency: "USDT",
    default_source: "okx",
    products: ["coinbot"],
    aliases: ["SOLUSDT", "SOL/USDT"],
    description: "Crypto spot market pair.",
  },
  {
    symbol: "XRP-USDT",
    name: "XRP / USDT Spot",
    exchange: "OKX",
    asset_type: "crypto",
    currency: "USDT",
    default_source: "okx",
    products: ["coinbot"],
    aliases: ["XRPUSDT", "XRP/USDT"],
    description: "Crypto spot market pair.",
  },
  {
    symbol: "DOGE-USDT",
    name: "Dogecoin / USDT Spot",
    exchange: "OKX",
    asset_type: "crypto",
    currency: "USDT",
    default_source: "okx",
    products: ["coinbot"],
    aliases: ["DOGEUSDT", "DOGE/USDT"],
    description: "Crypto spot market pair.",
  },
  {
    symbol: "ADA-USDT",
    name: "Cardano / USDT Spot",
    exchange: "OKX",
    asset_type: "crypto",
    currency: "USDT",
    default_source: "okx",
    products: ["coinbot"],
    aliases: ["ADAUSDT", "ADA/USDT"],
    description: "Crypto spot market pair.",
  },
] as const;

export function instrumentsForProduct(product: ProductId): SupportedInstrument[] {
  return MARKET_UNIVERSE.filter((instrument) => instrument.products.includes(product));
}

export function findInstrument(symbol: string): SupportedInstrument | undefined {
  const normalized = symbol.trim().toUpperCase();
  return MARKET_UNIVERSE.find(
    (instrument) =>
      instrument.symbol.toUpperCase() === normalized ||
      instrument.aliases.some((alias) => alias.toUpperCase() === normalized),
  );
}
