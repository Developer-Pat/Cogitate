import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

/**
 * Where a Saved run goes.
 *
 * ONE destination, chosen once (the design's §8: "one default destination the
 * user picks once"). The page PREFILLS the save dialog with it and remembers
 * whatever the person confirms, so saving a run to the same place twice is two
 * clicks rather than retyping a path.
 *
 * The empty string is meaningful: it means "the server's own default" — the
 * locator's destination — and the dialog says so rather than showing a blank the
 * person has to interpret. The value is a PATH STRING, because the file I/O is the
 * server's: this page never writes a file itself.
 */
interface TestingSavePreference {
  /** Empty = use the server's default destination. */
  saveDestination: string;
  setSaveDestination: (destination: string) => void;
}

const STORAGE_KEY = 'testing_save_destination';

export const useTestingSavePreference = create<TestingSavePreference>()(
  persist(
    (set) => ({
      saveDestination: '',
      setSaveDestination: (destination) => set({ saveDestination: destination }),
    }),
    { name: STORAGE_KEY, storage: createJSONStorage(() => localStorage) },
  ),
);

export default useTestingSavePreference;
