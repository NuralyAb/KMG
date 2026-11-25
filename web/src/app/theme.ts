import { createTheme, rem, type MantineColorsTuple } from '@mantine/core';

// Шкалы METU: контраст текста и элементов управления проверен (AA и выше).
const brand: MantineColorsTuple = [
  '#E6F3F7', '#CDE6EE', '#9CCCDD', '#67B1CB', '#3D9ABB', '#2389AF', '#0B6E8F', '#0A6180', '#085470', '#05465E',
];
const amber: MantineColorsTuple = [
  '#FFF6E5', '#FFEBC7', '#FFD891', '#FFC45A', '#FFB547', '#D98E0B', '#9A5B00', '#8A4F00', '#753F00', '#5E3200',
];
const green: MantineColorsTuple = [
  '#E6F5EC', '#CBE9D8', '#9BD3B5', '#69BB90', '#43A673', '#2B925F', '#1E7B4F', '#196A44', '#145839', '#0F452D',
];
const red: MantineColorsTuple = [
  '#FDECEA', '#F9D4D0', '#F0ACA5', '#E6827A', '#DC5F56', '#D1453C', '#C4322A', '#A8241D', '#8B1C16', '#6E1511',
];
const gray: MantineColorsTuple = [
  '#F4F7F8', '#EDF1F3', '#E1E8EB', '#D3DCE0', '#C8D2D7', '#8D9AA1', '#55636B', '#46535A', '#323D43', '#1B2327',
];

const FONT = "'IBM Plex Sans Variable', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

export const theme = createTheme({
  primaryColor: 'brand',
  primaryShade: { light: 6, dark: 4 },
  colors: { brand, amber, green, red, gray, orange: amber, yellow: amber, teal: green },
  fontFamily: FONT,
  headings: { fontFamily: FONT, fontWeight: '600' },
  // текст от 16 px: младшие ступени подняты до основной
  fontSizes: { xs: rem(16), sm: rem(16), md: rem(16), lg: rem(18), xl: rem(20) },
  lineHeights: { xs: '1.4', sm: '1.45', md: '1.55', lg: '1.5', xl: '1.4' },
  defaultRadius: 'sm',
  radius: { xs: rem(4), sm: rem(6), md: rem(6), lg: rem(8), xl: rem(16) },
  cursorType: 'pointer',
  focusRing: 'auto',
  autoContrast: true,
  components: {
    Button: { defaultProps: { radius: 'sm' }, styles: { label: { fontWeight: 500 } } },
    Tooltip: { defaultProps: { withArrow: false, openDelay: 300 } },
    Modal: { defaultProps: { radius: 'lg', centered: true } },
  },
});
