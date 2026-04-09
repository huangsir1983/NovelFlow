import '@testing-library/jest-dom/vitest';

// React 19 requires this global to flush concurrent renders inside act()
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
