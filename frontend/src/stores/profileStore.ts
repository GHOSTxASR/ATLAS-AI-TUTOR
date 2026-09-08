import { getErrorMessage } from "../utils/errors";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { profileApi } from "../api/profiles";
import { Profile, ProfileCreate, ProfileUpdate } from "../types";

interface ProfileState {
  profiles: Profile[];
  activeProfileId: string | null;
  isLoading: boolean;
  error: string | null;

  loadProfiles: () => Promise<void>;
  createProfile: (data: ProfileCreate) => Promise<void>;
  updateProfile: (id: string, data: ProfileUpdate) => Promise<void>;
  deleteProfile: (id: string) => Promise<void>;
  setActiveProfile: (id: string | null) => void;
}

const PROFILE_STORAGE_KEY = "atlas-profile-storage";
const LEGACY_PROFILE_STORAGE_KEY = "learningos-profile-storage";

// Carry the selected profile across the rename; without this an existing
// install comes back with no active profile and an empty dashboard.
if (typeof localStorage !== "undefined") {
  const legacy = localStorage.getItem(LEGACY_PROFILE_STORAGE_KEY);
  if (legacy && !localStorage.getItem(PROFILE_STORAGE_KEY)) {
    localStorage.setItem(PROFILE_STORAGE_KEY, legacy);
  }
  if (legacy) localStorage.removeItem(LEGACY_PROFILE_STORAGE_KEY);
}

export const useProfileStore = create<ProfileState>()(
  persist(
    (set, get) => ({
      profiles: [],
      activeProfileId: null,
      isLoading: false,
      error: null,

      loadProfiles: async () => {
        set({ isLoading: true, error: null });
        try {
          const profiles = await profileApi.getAll();
          set({ profiles, isLoading: false });
          // If no active profile but profiles exist, select the first one
          const { activeProfileId } = get();
          if (!activeProfileId && profiles.length > 0) {
            set({ activeProfileId: profiles[0].id });
          } else if (activeProfileId && !profiles.find((p) => p.id === activeProfileId)) {
            // If active profile was deleted elsewhere
            set({ activeProfileId: profiles.length > 0 ? profiles[0].id : null });
          }
        } catch (err) {
          set({ error: getErrorMessage(err, "Failed to load profiles"), isLoading: false });
        }
      },

      createProfile: async (data: ProfileCreate) => {
        set({ isLoading: true, error: null });
        try {
          const newProfile = await profileApi.create(data);
          const profiles = [...get().profiles, newProfile];
          set({ profiles, activeProfileId: newProfile.id, isLoading: false });
        } catch (err) {
          set({ error: getErrorMessage(err, "Failed to create profile"), isLoading: false });
        }
      },

      updateProfile: async (id: string, data: ProfileUpdate) => {
        set({ isLoading: true, error: null });
        try {
          const updatedProfile = await profileApi.update(id, data);
          const profiles = get().profiles.map((p) => (p.id === id ? updatedProfile : p));
          set({ profiles, isLoading: false });
        } catch (err) {
          set({ error: getErrorMessage(err, "Failed to update profile"), isLoading: false });
        }
      },

      deleteProfile: async (id: string) => {
        set({ isLoading: true, error: null });
        try {
          await profileApi.delete(id);
          const profiles = get().profiles.filter((p) => p.id !== id);
          const { activeProfileId } = get();
          set({
            profiles,
            activeProfileId: activeProfileId === id ? (profiles.length > 0 ? profiles[0].id : null) : activeProfileId,
            isLoading: false,
          });
        } catch (err) {
          set({ error: getErrorMessage(err, "Failed to delete profile"), isLoading: false });
        }
      },

      setActiveProfile: (id: string | null) => {
        set({ activeProfileId: id });
      },
    }),
    {
      name: PROFILE_STORAGE_KEY,
      // Only persist the activeProfileId. Profiles themselves should be loaded from the backend.
      partialize: (state) => ({ activeProfileId: state.activeProfileId }),
    }
  )
);
