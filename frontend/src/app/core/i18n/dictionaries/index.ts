import type { AppLocale } from '../locale.service';
import { en } from './en';
import { es } from './es';
import type { Dictionary } from './types';

export type { Dictionary } from './types';

export const DICTIONARIES: Record<AppLocale, Dictionary> = { es, en };
